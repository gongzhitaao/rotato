"""Tests for minting GitHub App installation tokens."""

import cryptography.hazmat.primitives.asymmetric.rsa as rsa
import httpx2
import jwt
import pytest
from cryptography.hazmat.primitives import serialization

import rotato.consumer.github as github


def _pem():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()
    public = key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return private, public


class _Resp:
    def raise_for_status(self):
        pass

    def json(self):
        return {"token": "ghs_installation_token"}


def _capturing_post(captured):
    def fake_post(url, headers=None, **_kwargs):
        captured["url"] = url
        captured["auth"] = headers["Authorization"]
        return _Resp()

    return fake_post


def _claims(captured, public):
    return jwt.decode(
        captured["auth"].removeprefix("Bearer "), public, algorithms=["RS256"]
    )


def test_mint_token_returns_installation_token(monkeypatch):
    private, _ = _pem()
    captured = {}
    monkeypatch.setattr(github.httpx2, "post", _capturing_post(captured))
    assert (
        github.mint_token(private, "123456", "789") == "ghs_installation_token"
    )
    assert captured["url"].endswith("/app/installations/789/access_tokens")


def test_mint_token_signs_app_id_as_iss(monkeypatch):
    private, public = _pem()
    captured = {}
    monkeypatch.setattr(github.httpx2, "post", _capturing_post(captured))
    github.mint_token(private, "123456", "789")
    claims = _claims(captured, public)
    assert claims["iss"] == "123456"
    assert 0 < claims["exp"] - claims["iat"] <= 600


def test_mint_token_signs_string_client_id_as_iss(monkeypatch):
    private, public = _pem()
    captured = {}
    monkeypatch.setattr(github.httpx2, "post", _capturing_post(captured))
    github.mint_token(private, "Iv1.abc123", "789")
    assert _claims(captured, public)["iss"] == "Iv1.abc123"


def test_mint_token_raises_on_http_error(monkeypatch):
    private, _ = _pem()
    req = httpx2.Request("POST", "https://api.github.com/x")
    monkeypatch.setattr(
        github.httpx2, "post", lambda *a, **k: httpx2.Response(401, request=req)
    )
    with pytest.raises(httpx2.HTTPStatusError):
        github.mint_token(private, "1", "2")

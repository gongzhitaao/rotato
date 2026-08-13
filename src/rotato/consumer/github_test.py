"""Tests for minting GitHub App installation tokens."""

import cryptography.hazmat.primitives.asymmetric.rsa as rsa
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


class _CapturingResponse:
    def __init__(self, captured):
        self._captured = captured

    def raise_for_status(self):
        pass

    def json(self):
        return {"token": "ghs_installation_token"}


def _install_fakes(monkeypatch, pem, captured):
    monkeypatch.setattr(github.fetch, "fetch_value", lambda s: pem)

    def fake_post(url, headers=None, **_kwargs):
        captured["url"] = url
        captured["auth"] = headers["Authorization"]
        return _CapturingResponse(captured)

    monkeypatch.setattr(github.httpx, "post", fake_post)


def test_mint_token_returns_installation_token(monkeypatch):
    private, _ = _pem()
    captured = {}
    _install_fakes(monkeypatch, private, captured)
    token = github.mint_token("pem", "123456", "789")
    assert token == "ghs_installation_token"
    assert captured["url"].endswith("/app/installations/789/access_tokens")


def test_mint_token_signs_app_id_as_iss(monkeypatch):
    private, public = _pem()
    captured = {}
    _install_fakes(monkeypatch, private, captured)
    github.mint_token("pem", "123456", "789")

    jwt_str = captured["auth"].removeprefix("Bearer ")
    claims = jwt.decode(jwt_str, public, algorithms=["RS256"])
    assert claims["iss"] == "123456"


def test_mint_token_signs_string_client_id_as_iss(monkeypatch):
    private, public = _pem()
    captured = {}
    _install_fakes(monkeypatch, private, captured)
    github.mint_token("pem", "Iv1.abc123", "789")

    jwt_str = captured["auth"].removeprefix("Bearer ")
    claims = jwt.decode(jwt_str, public, algorithms=["RS256"])
    assert claims["iss"] == "Iv1.abc123"


def test_mint_token_raises_on_http_error(monkeypatch):
    private, _ = _pem()
    monkeypatch.setattr(github.fetch, "fetch_value", lambda s: private)

    def boom(*_args, **_kwargs):
        class R:
            def raise_for_status(self):
                raise RuntimeError("401")

        return R()

    monkeypatch.setattr(github.httpx, "post", boom)
    with pytest.raises(RuntimeError):
        github.mint_token("pem", "123", "789")

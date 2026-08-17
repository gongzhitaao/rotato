"""Tests for the GitLab rotator."""

# Tests exercise the module's private _rotate.
# pylint: disable=protected-access

import httpx2
import pytest

import rotato.rotators.gitlab as gl


def _resp(status, json=None, url="https://gitlab.com/x"):
    req = httpx2.Request("POST", url)
    if json is None:
        return httpx2.Response(status, request=req)
    return httpx2.Response(status, json=json, request=req)


def test_rotate_returns_token(monkeypatch):
    monkeypatch.setattr(
        gl.httpx2, "post", lambda url, **k: _resp(200, {"token": "NEWTOKEN"})
    )
    assert gl._rotate("OLD", "https://gitlab.com", 30) == "NEWTOKEN"


def test_rotate_posts_to_configured_host(monkeypatch):
    seen = {}
    monkeypatch.setattr(
        gl.httpx2,
        "post",
        lambda url, **k: seen.update(url=url) or _resp(200, {"token": "T"}),
    )
    gl._rotate("OLD", "https://gitlab.example.com", 30)
    assert seen["url"].startswith("https://gitlab.example.com/api/v4/")


def test_rotate_raises_on_http_error(monkeypatch):
    monkeypatch.setattr(gl.httpx2, "post", lambda url, **k: _resp(403))
    with pytest.raises(httpx2.HTTPStatusError):
        gl._rotate("OLD", "https://gitlab.com", 30)


def test_rotator_config_defaults():
    assert gl.ROTATOR.config({"rotato": "gitlab"}) == {
        "host": "https://gitlab.com",
        "expiry": "30",
    }


def test_rotator_config_overrides():
    tags = {"host": "https://gl.internal", "expiry": "7"}
    assert gl.ROTATOR.config(tags) == tags


def test_rotate_via_rotator_uses_config(monkeypatch):
    monkeypatch.setattr(
        gl.httpx2, "post", lambda url, **k: _resp(200, {"token": "NEW"})
    )
    cfg = {"host": "https://gitlab.com", "expiry": "7"}
    assert gl.ROTATOR.rotate("OLD", cfg) == "NEW"

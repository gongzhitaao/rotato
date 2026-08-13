"""Tests for the GitLab PAT rotator."""

# Tests exercise the module's private _rotate and a fake store's internals.
# pylint: disable=protected-access

import httpx2
import pytest

import rotato.rotators.gitlab_pat as gp


def _resp(status, json=None, url="https://gitlab.com/x"):
    req = httpx2.Request("POST", url)
    if json is None:
        return httpx2.Response(status, request=req)
    return httpx2.Response(status, json=json, request=req)


def test_rotate_returns_token(monkeypatch):
    monkeypatch.setattr(
        gp.httpx2, "post", lambda url, **k: _resp(200, {"token": "NEWTOKEN"})
    )
    assert gp._rotate("OLD") == "NEWTOKEN"


def test_rotate_raises_on_http_error(monkeypatch):
    monkeypatch.setattr(gp.httpx2, "post", lambda url, **k: _resp(403))
    with pytest.raises(httpx2.HTTPStatusError):
        gp._rotate("OLD")


class _FakeStore:
    def __init__(self, value):
        self._v = {"sid": value}

    def get_value(self, sid):
        return self._v[sid]

    def set_value(self, sid, value):
        self._v[sid] = value


def test_run_end_to_end(monkeypatch):
    monkeypatch.setattr(
        gp.httpx2, "post", lambda url, **k: _resp(200, {"token": "NEWTOKEN"})
    )
    monkeypatch.setenv("GITLAB_PAT_SECRET_ID", "sid")
    store = _FakeStore("OLD")
    gp.run(store)
    assert store._v["sid"] == "NEWTOKEN"

import httpx
import pytest

import rotato.rotators.gitlab_pat as gp


def _resp(status, json=None, url="https://gitlab.com/x"):
    req = httpx.Request("POST", url)
    if json is None:
        return httpx.Response(status, request=req)
    return httpx.Response(status, json=json, request=req)


def test_rotate_returns_token(monkeypatch):
    monkeypatch.setattr(gp.httpx, "post", lambda url, **k: _resp(200, {"token": "NEWTOKEN"}))
    assert gp._rotate("OLD") == "NEWTOKEN"


def test_rotate_raises_on_http_error(monkeypatch):
    monkeypatch.setattr(gp.httpx, "post", lambda url, **k: _resp(403))
    with pytest.raises(httpx.HTTPStatusError):
        gp._rotate("OLD")


class _FakeStore:
    def __init__(self, value):
        self._v = {"sid": value}

    def get_value(self, sid):
        return self._v[sid]

    def set_value(self, sid, value):
        self._v[sid] = value


def test_run_end_to_end(monkeypatch):
    monkeypatch.setattr(gp.httpx, "post", lambda url, **k: _resp(200, {"token": "NEWTOKEN"}))
    monkeypatch.setenv("GITLAB_PAT_SECRET_ID", "sid")
    store = _FakeStore("OLD")
    gp.run(store)
    assert store._v["sid"] == "NEWTOKEN"

"""Tests for the git credential-helper adapter."""

import pytest

import rotato.consumer.gitcredential as gc


def test_get_token_mode_emits_password(monkeypatch):
    monkeypatch.setattr(gc.fetch, "fetch_value", lambda s: "PAT123")
    out = gc.emit_credential("gitlab-pat", "get")
    assert out == "password=PAT123\n"


def test_github_mode_emits_username_and_password(monkeypatch):
    monkeypatch.setattr(gc.github, "mint_token", lambda s, a, i, api: "ghs_tok")
    out = gc.emit_credential(
        "pem", "get", is_github=True, app_id="1", installation_id="2"
    )
    assert out == "username=x-access-token\npassword=ghs_tok\n"


def test_store_and_erase_are_noops(monkeypatch):
    monkeypatch.setattr(gc.fetch, "fetch_value", lambda s: "unused")
    assert gc.emit_credential("gitlab-pat", "store") == ""
    assert gc.emit_credential("gitlab-pat", "erase") == ""
    assert gc.emit_credential("gitlab-pat", "") == ""


def test_value_with_newline_is_rejected(monkeypatch):
    # a newline in the value would corrupt git's line-oriented protocol.
    monkeypatch.setattr(gc.fetch, "fetch_value", lambda s: "abc\nhost=evil")
    with pytest.raises(SystemExit):
        gc.emit_credential("gitlab-pat", "get")

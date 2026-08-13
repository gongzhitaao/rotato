"""Tests for consumer paths and the name -> uuid registry."""

import pytest

import rotato.consumer.config as config

_UUID = "12345678-1234-1234-1234-123456789abc"


@pytest.fixture(autouse=True)
def _isolate(tmp_path, monkeypatch):
    monkeypatch.setenv("ROTATO_CONFIG_DIR", str(tmp_path))
    monkeypatch.delenv("ROTATO_TOKEN_FILE", raising=False)
    monkeypatch.delenv("ROTATO_SECRETS_FILE", raising=False)


def test_resolve_passes_uuid_through():
    assert config.resolve(_UUID) == _UUID


def test_resolve_maps_name_to_uuid():
    config.record_secret("gitlab-pat", _UUID)
    assert config.resolve("gitlab-pat") == _UUID


def test_resolve_unknown_name_exits():
    with pytest.raises(SystemExit):
        config.resolve("no-such-name")


def test_record_secret_roundtrip_and_dedupe():
    config.record_secret("a", _UUID)
    config.record_secret("a", "other-uuid")  # same name replaces
    config.record_secret("b", _UUID)
    assert config.load_secrets() == {"a": "other-uuid", "b": _UUID}


def test_load_secrets_missing_file_is_empty():
    assert config.load_secrets() == {}


def test_read_token_strips_and_reads(tmp_path, monkeypatch):
    token = tmp_path / "token"
    token.write_text("  sekret\n")
    monkeypatch.setenv("ROTATO_TOKEN_FILE", str(token))
    assert config.read_token() == "sekret"


def test_read_token_missing_exits():
    with pytest.raises(SystemExit):
        config.read_token()

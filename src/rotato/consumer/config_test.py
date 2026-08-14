"""Tests for consumer paths and the installed-secret registry."""

import json

import pytest

import rotato.consumer.config as config

_UUID = "12345678-1234-1234-1234-123456789abc"


@pytest.fixture(autouse=True)
def _isolate(tmp_path, monkeypatch):
    monkeypatch.setenv("ROTATO_CONFIG_DIR", str(tmp_path))
    monkeypatch.delenv("ROTATO_TOKEN_FILE", raising=False)
    monkeypatch.delenv("ROTATO_SECRETS_FILE", raising=False)


def test_record_and_resolve_by_name():
    config.record_secret("gitlab-pat", config.Entry(uuid=_UUID))
    name, entry = config.resolve("gitlab-pat")
    assert name == "gitlab-pat"
    assert entry.uuid == _UUID
    assert entry.kind == config.KIND_TOKEN


def test_resolve_by_uuid_reverse_lookup():
    config.record_secret("gitlab-pat", config.Entry(uuid=_UUID))
    name, entry = config.resolve(_UUID)
    assert name == "gitlab-pat"
    assert entry.uuid == _UUID


def test_resolve_uninstalled_name_exits():
    with pytest.raises(SystemExit):
        config.resolve("no-such-name")


def test_resolve_uninstalled_uuid_exits():
    with pytest.raises(SystemExit):
        config.resolve(_UUID)


def test_github_app_entry_roundtrip():
    config.record_secret(
        "gh",
        config.Entry(
            uuid=_UUID,
            kind=config.KIND_GITHUB_APP,
            app_id="123",
            installation_id="456",
        ),
    )
    _, entry = config.resolve("gh")
    assert entry.kind == config.KIND_GITHUB_APP
    assert entry.app_id == "123"
    assert entry.installation_id == "456"


def test_record_dedupes_by_name():
    config.record_secret("a", config.Entry(uuid=_UUID))
    config.record_secret("a", config.Entry(uuid="other"))
    secrets = config.load_secrets()
    assert set(secrets) == {"a"}
    assert secrets["a"].uuid == "other"


def test_record_preserves_other_entries():
    config.record_secret("a", config.Entry(uuid="UA"))
    config.record_secret("b", config.Entry(uuid="UB"))
    config.record_secret("c", config.Entry(uuid="UC"))
    secrets = config.load_secrets()
    assert set(secrets) == {"a", "b", "c"}
    assert secrets["a"].uuid == "UA"
    assert secrets["b"].uuid == "UB"


def test_reads_legacy_uuid_string_format(tmp_path):
    # 0.1.x wrote {name: uuid}; read it as a token entry.
    (tmp_path / "secrets.json").write_text(
        json.dumps({"legacy": _UUID}), encoding="utf-8"
    )
    _, entry = config.resolve("legacy")
    assert entry.uuid == _UUID
    assert entry.kind == config.KIND_TOKEN


def test_load_secrets_missing_is_empty():
    assert not config.load_secrets()


def test_load_secrets_non_utf8_is_empty(tmp_path):
    # a corrupt (non-UTF-8) file must not crash a read (completion needs this).
    (tmp_path / "secrets.json").write_bytes(b"\xff\xfe not valid utf-8")
    assert not config.load_secrets()


def test_read_token(tmp_path, monkeypatch):
    token = tmp_path / "token"
    token.write_text("  sekret\n")
    monkeypatch.setenv("ROTATO_TOKEN_FILE", str(token))
    assert config.read_token() == "sekret"


def test_read_token_missing_exits():
    with pytest.raises(SystemExit):
        config.read_token()

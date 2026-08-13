"""Tests for registering a secret (rotato install)."""

# Tests stub the module's private helpers; the fixture-name-as-argument (used
# for its side effects) is the standard pytest pattern.
# pylint: disable=protected-access,redefined-outer-name,unused-argument

import stat

import pytest

import rotato.consumer.config as config
import rotato.consumer.install as install


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("ROTATO_CONFIG_DIR", str(tmp_path))
    monkeypatch.setattr(
        install.getpass, "getpass", lambda prompt="": "TOKEN123"
    )
    return tmp_path


def test_token_records_entry_and_writes_token(env):
    rc = install.run(install.InstallArgs(uuid="U1", name="gitlab-pat"))
    assert rc == 0
    token_file = env / "token"
    assert token_file.read_text() == "TOKEN123"
    assert stat.S_IMODE(token_file.stat().st_mode) == 0o600
    entry = config.load_secrets()["gitlab-pat"]
    assert entry.uuid == "U1"
    assert entry.kind == config.KIND_TOKEN


def test_github_records_app_metadata(env):
    install.run(
        install.InstallArgs(
            uuid="P1",
            name="gh",
            github=True,
            app_id="123",
            installation_id="456",
        )
    )
    entry = config.load_secrets()["gh"]
    assert entry.kind == config.KIND_GITHUB_APP
    assert entry.app_id == "123"
    assert entry.installation_id == "456"


def test_default_name_from_bitwarden(env, monkeypatch):
    monkeypatch.setattr(install, "_default_name", lambda uuid: "bwskey")
    install.run(install.InstallArgs(uuid="U9"))
    assert "bwskey" in config.load_secrets()


def test_preexisting_wide_perm_token_is_tightened(env):
    token_file = env / "token"
    token_file.write_text("")
    token_file.chmod(0o644)
    install.run(install.InstallArgs(uuid="U1", name="n"))
    assert stat.S_IMODE(token_file.stat().st_mode) == 0o600


def test_warns_on_name_collision_with_different_uuid(env, capsys):
    install.run(install.InstallArgs(uuid="U1", name="x"))
    install.run(install.InstallArgs(uuid="U2", name="x"))
    assert "already points at U1" in capsys.readouterr().err
    assert config.load_secrets()["x"].uuid == "U2"


def test_dry_run_has_no_side_effects(env):
    rc = install.run(install.InstallArgs(uuid="U1", name="n", dry_run=True))
    assert rc == 0
    assert not (env / "token").exists()
    assert not config.load_secrets()

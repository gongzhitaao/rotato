"""Tests for the real (side-effecting) install path."""

# Tests exercise the module's private helpers (_rotato_bin, _helper_cmd); the
# fixture-name-as-argument shadowing is the standard pytest pattern.
# pylint: disable=protected-access,redefined-outer-name

import stat

import pytest

import rotato.consumer.config as config
import rotato.consumer.install as install


@pytest.fixture
def env(tmp_path, monkeypatch):
    """Isolate config state and stub the prompt / git / binary lookup."""
    monkeypatch.setenv("ROTATO_CONFIG_DIR", str(tmp_path))
    monkeypatch.setattr(
        install.getpass, "getpass", lambda prompt="": "TOKEN123"
    )
    calls = []
    monkeypatch.setattr(
        install.subprocess, "run", lambda argv, **k: calls.append(argv)
    )
    monkeypatch.setattr(install, "_rotato_bin", lambda: "/opt/rotato")
    return tmp_path, calls


def test_token_mode_writes_token_secrets_and_git_config(env):
    tmp_path, calls = env
    rc = install.run(
        install.InstallArgs(secret_id="uuid-1", user="alice", name="gitlab-pat")
    )
    assert rc == 0

    token_file = tmp_path / "token"
    assert token_file.read_text() == "TOKEN123"
    assert stat.S_IMODE(token_file.stat().st_mode) == 0o600

    assert config.load_secrets() == {"gitlab-pat": "uuid-1"}

    # username + helper both set with --replace-all.
    assert [
        "git",
        "config",
        "--global",
        "--replace-all",
        "credential.https://gitlab.com.username",
        "alice",
    ] in calls
    helper = next(c for c in calls if c[-2].endswith(".helper"))
    assert helper[-1] == "!/opt/rotato git-credential uuid-1"


def test_preexisting_wide_perm_token_is_tightened(env):
    # security fix: an existing empty, world-readable token file must end 0600.
    tmp_path, _ = env
    token_file = tmp_path / "token"
    token_file.write_text("")
    token_file.chmod(0o644)

    install.run(install.InstallArgs(secret_id="uuid-1", user="alice", name="n"))
    assert stat.S_IMODE(token_file.stat().st_mode) == 0o600


def test_existing_nonempty_token_is_kept(env):
    tmp_path, _ = env
    token_file = tmp_path / "token"
    token_file.write_text("EXISTING")

    install.run(install.InstallArgs(secret_id="uuid-1", user="alice", name="n"))
    assert token_file.read_text() == "EXISTING"  # not re-prompted/clobbered


def test_github_mode_helper_and_no_username(env):
    _, calls = env
    install.run(
        install.InstallArgs(
            secret_id="pem-1",
            mode="github",
            app_id="12345",
            installation_id="678",
            name="gh",
        )
    )
    # github mode configures a helper but never a username.
    assert not any(c[-2].endswith(".username") for c in calls)
    helper = next(c for c in calls if c[-2].endswith(".helper"))
    assert helper[-2] == "credential.https://github.com.helper"
    assert helper[-1] == (
        "!/opt/rotato git-credential --github "
        "--app-id 12345 --installation-id 678 pem-1"
    )


def test_dry_run_has_no_side_effects(env):
    tmp_path, calls = env
    rc = install.run(
        install.InstallArgs(secret_id="uuid-1", user="alice", dry_run=True)
    )
    assert rc == 0
    assert not (tmp_path / "token").exists()
    assert calls == []


def test_helper_cmd_shell_quotes_spaced_path():
    args = install.InstallArgs(secret_id="uuid-1", user="alice")
    cmd = install._helper_cmd(args, "/opt/My Tools/rotato")
    assert "'/opt/My Tools/rotato'" in cmd

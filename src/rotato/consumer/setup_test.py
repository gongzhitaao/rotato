"""Tests for wiring git to an installed secret (rotato setup)."""

# Tests stub the module's private helpers; the fixture-name-as-argument (used
# for its side effects) is the standard pytest pattern.
# pylint: disable=protected-access,redefined-outer-name,unused-argument

import pytest

import rotato.consumer.config as config
import rotato.consumer.setup as setup


@pytest.fixture
def calls(tmp_path, monkeypatch):
    monkeypatch.setenv("ROTATO_CONFIG_DIR", str(tmp_path))
    recorded = []
    monkeypatch.setattr(
        setup.subprocess, "run", lambda argv, **k: recorded.append(argv)
    )
    monkeypatch.setattr(setup, "_rotato_bin", lambda: "/opt/rotato")
    return recorded


def _helper_value(calls):
    return next(c for c in calls if c[-2].endswith(".helper"))[-1]


def test_gitlab_writes_username_and_password_helper(calls):
    config.record_secret("gitlab-pat", config.Entry(uuid="U"))
    rc = setup.run(
        setup.SetupArgs(
            target="gitlab", name_or_uuid="gitlab-pat", user="alice"
        )
    )
    assert rc == 0
    assert [
        "git",
        "config",
        "--global",
        "--replace-all",
        "credential.https://gitlab.com.username",
        "alice",
    ] in calls
    helper = _helper_value(calls)
    assert helper.startswith("!f() {")
    assert "/opt/rotato print gitlab-pat" in helper
    assert "username=" not in helper  # token mode: password only


def test_github_writes_helper_and_no_username_config(calls):
    config.record_secret(
        "gh",
        config.Entry(
            uuid="P",
            kind=config.KIND_GITHUB_APP,
            app_id="1",
            installation_id="2",
        ),
    )
    setup.run(setup.SetupArgs(target="github", name_or_uuid="gh"))
    assert not any(c[-2].endswith(".username") for c in calls)
    helper = _helper_value(calls)
    assert "username=x-access-token" in helper
    assert "/opt/rotato print gh" in helper


def test_git_target_writes_username_and_helper(calls):
    config.record_secret("tok", config.Entry(uuid="U"))
    rc = setup.run(
        setup.SetupArgs(
            target="git",
            name_or_uuid="tok",
            user="bob",
            host="git.example.com",
        )
    )
    assert rc == 0
    assert [
        "git",
        "config",
        "--global",
        "--replace-all",
        "credential.https://git.example.com.username",
        "bob",
    ] in calls
    helper = _helper_value(calls)
    assert "/opt/rotato print tok" in helper
    assert "username=" not in helper


def test_helper_fails_loudly_on_print_error(calls):
    config.record_secret("gitlab-pat", config.Entry(uuid="U"))
    setup.run(
        setup.SetupArgs(target="gitlab", name_or_uuid="gitlab-pat", user="a")
    )
    assert "|| exit 1" in _helper_value(calls)


def test_gitlab_requires_user(calls):
    config.record_secret("gitlab-pat", config.Entry(uuid="U"))
    rc = setup.run(setup.SetupArgs(target="gitlab", name_or_uuid="gitlab-pat"))
    assert rc == 2
    assert calls == []


def test_git_requires_host(calls):
    config.record_secret("x", config.Entry(uuid="U"))
    rc = setup.run(
        setup.SetupArgs(target="git", name_or_uuid="x", user="alice")
    )
    assert rc == 2


def test_github_rejects_token_kind(calls):
    config.record_secret("gitlab-pat", config.Entry(uuid="U"))
    rc = setup.run(setup.SetupArgs(target="github", name_or_uuid="gitlab-pat"))
    assert rc == 2


def test_gitlab_rejects_github_app_kind(calls):
    config.record_secret(
        "gh", config.Entry(uuid="P", kind=config.KIND_GITHUB_APP)
    )
    rc = setup.run(
        setup.SetupArgs(target="gitlab", name_or_uuid="gh", user="alice")
    )
    assert rc == 2


def test_uninstalled_exits(calls):
    with pytest.raises(SystemExit):
        setup.run(
            setup.SetupArgs(target="gitlab", name_or_uuid="nope", user="a")
        )


def test_shell_quotes_spaced_rotato_path(monkeypatch, calls):
    monkeypatch.setattr(setup, "_rotato_bin", lambda: "/opt/My Tools/rotato")
    config.record_secret("gitlab-pat", config.Entry(uuid="U"))
    setup.run(
        setup.SetupArgs(target="gitlab", name_or_uuid="gitlab-pat", user="a")
    )
    assert "'/opt/My Tools/rotato' print gitlab-pat" in _helper_value(calls)

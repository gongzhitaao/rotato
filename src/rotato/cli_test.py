"""Tests for the rotato CLI dispatcher."""

# Completion tests reach the module's private completer helpers and introspect
# argparse internals.
# pylint: disable=protected-access

import argparse
import types

import argcomplete

import rotato.cli as cli

# --- tag-driven batch rotation (server side) ---


def _stub_batch(monkeypatch, report=None):
    """Wire refresh to a fake Bitwarden client + a canned roster report."""
    monkeypatch.setenv("BWS_ORGANIZATION_ID", "org")
    monkeypatch.setattr(
        cli.bws,
        "BwsClient",
        lambda: types.SimpleNamespace(list_secrets=lambda org: ["S"]),
    )
    rep = report or cli.roster.Report(
        rotated=[cli.roster.Item("i", "k", "gitlab", "rotated")]
    )
    monkeypatch.setattr(cli.roster, "rotate_tagged", lambda *a, **k: rep)
    return rep


def test_refresh_runs_batch(monkeypatch, capsys):
    _stub_batch(monkeypatch)
    assert cli.main(["refresh"]) == 0
    assert "roster: rotated 1" in capsys.readouterr().out


def test_bare_rotato_runs_batch(monkeypatch):
    _stub_batch(monkeypatch)
    assert cli.main([]) == 0


def test_refresh_missing_org_returns_2(monkeypatch, capsys):
    monkeypatch.delenv("BWS_ORGANIZATION_ID", raising=False)
    assert cli.main(["refresh"]) == 2
    assert "BWS_ORGANIZATION_ID" in capsys.readouterr().err


def test_refresh_failed_report_returns_1(monkeypatch):
    report = cli.roster.Report(
        failed=[cli.roster.Item("i", "k", "gitlab", "failed", "boom")]
    )
    _stub_batch(monkeypatch, report)
    assert cli.main(["refresh"]) == 1


# --- consumer subcommands ---


def test_print_outputs_credential(monkeypatch, capsys):
    monkeypatch.setattr(cli.credential, "usable_credential", lambda s: "SECRET")
    assert cli.main(["print", "gitlab-pat"]) == 0
    assert capsys.readouterr().out.strip() == "SECRET"


def test_install_github_requires_app_id(capsys):
    assert cli.main(["install", "some-uuid", "--github"]) == 2
    assert "--app-id" in capsys.readouterr().err


def test_install_app_id_without_github_errors(capsys):
    assert cli.main(["install", "some-uuid", "--app-id", "1"]) == 2
    assert "--github" in capsys.readouterr().err


def test_install_dry_run(monkeypatch, capsys, tmp_path):
    monkeypatch.setenv("ROTATO_CONFIG_DIR", str(tmp_path))
    assert cli.main(["install", "some-uuid", "--name", "n", "--dry-run"]) == 0
    assert "dry run" in capsys.readouterr().out


def test_setup_dry_run(monkeypatch, capsys, tmp_path):
    monkeypatch.setenv("ROTATO_CONFIG_DIR", str(tmp_path))
    cli.config.record_secret("gl", cli.config.Entry(uuid="U"))
    rc = cli.main(["setup", "gitlab", "gl", "--user", "alice", "--dry-run"])
    assert rc == 0
    assert "dry run" in capsys.readouterr().out


def _fake_registry(monkeypatch):
    knob = cli.rotators.Knob("host", "https://gitlab.com", "instance URL")
    rotator = cli.rotators.Rotator(
        name="gitlab",
        rotate=lambda old, cfg: old,
        knobs=(knob,),
        help="GitLab PAT",
    )
    monkeypatch.setattr(cli.rotators, "REGISTRY", {"gitlab": rotator})


def test_list_rotators(monkeypatch, capsys):
    _fake_registry(monkeypatch)
    assert cli.main(["list", "rotators"]) == 0
    out = capsys.readouterr().out
    assert "gitlab" in out and "GitLab PAT" in out


def test_list_tags(monkeypatch, capsys):
    _fake_registry(monkeypatch)
    assert cli.main(["list", "tags"]) == 0
    out = capsys.readouterr().out
    assert "#rotato=<type>" in out
    assert "#host=<v>" in out
    assert "https://gitlab.com" in out


def test_list_secrets(monkeypatch, capsys, tmp_path):
    monkeypatch.setenv("ROTATO_CONFIG_DIR", str(tmp_path))
    cli.config.record_secret("gl", cli.config.Entry(uuid="U"))
    assert cli.main(["list", "secrets"]) == 0
    assert "gl\ttoken\tU" in capsys.readouterr().out


# --- shell completion ---


def test_complete_secrets(monkeypatch, tmp_path):
    monkeypatch.setenv("ROTATO_CONFIG_DIR", str(tmp_path))
    cli.config.record_secret("gitlab-pat", cli.config.Entry(uuid="U1"))
    cli.config.record_secret("npm-token", cli.config.Entry(uuid="U2"))
    assert cli._complete_secrets("gi") == ["gitlab-pat"]
    assert set(cli._complete_secrets("")) == {"gitlab-pat", "npm-token"}


def _subparser(parser, name):
    action = next(
        a for a in parser._actions if isinstance(a, argparse._SubParsersAction)
    )
    return action.choices[name]


def _completer_of(subparser, dest):
    action = next(a for a in subparser._actions if a.dest == dest)
    return getattr(action, "completer", None)


def test_completers_attached_to_actions():
    parser = cli._build_parser()
    assert (
        _completer_of(_subparser(parser, "print"), "secret")
        is cli._complete_secrets
    )
    assert (
        _completer_of(_subparser(parser, "setup"), "secret")
        is cli._complete_secrets
    )


def test_main_invokes_autocomplete_under_env_guard(monkeypatch):
    seen = {}
    monkeypatch.setattr(
        argcomplete, "autocomplete", lambda parser: seen.setdefault("p", parser)
    )
    monkeypatch.setattr(cli.rotators, "REGISTRY", {})
    # Without the env var the guard skips autocomplete...
    assert cli.main(["list", "rotators"]) == 0
    assert "p" not in seen
    # ...with it set, main invokes autocomplete on the built parser.
    monkeypatch.setenv("_ARGCOMPLETE", "1")
    assert cli.main(["list", "rotators"]) == 0
    assert isinstance(seen.get("p"), argparse.ArgumentParser)

"""Tests for the rotato CLI dispatcher."""

import rotato.cli as cli

# --- legacy server-side path (container ENTRYPOINT ["rotato"]) ---


def test_unknown_rotator_returns_2(capsys):
    assert cli.main(["definitely-not-a-rotator"]) == 2
    assert "unknown rotator" in capsys.readouterr().err


def test_no_name_returns_2(monkeypatch):
    monkeypatch.delenv("ROTATOR", raising=False)
    assert cli.main([]) == 2


def test_run_subcommand_unknown_rotator_returns_2(capsys):
    assert cli.main(["run", "nope"]) == 2
    assert "unknown rotator" in capsys.readouterr().err


def _stub_registry(monkeypatch):
    """Register a fake rotator and a fake client; return the call recorder."""
    seen = {}
    monkeypatch.setattr(
        cli.rotators,
        "REGISTRY",
        {"myrot": lambda store: seen.update(store=store)},
    )
    monkeypatch.setattr(cli.bws, "BwsClient", lambda: "FAKE_CLIENT")
    return seen


def test_legacy_bare_name_dispatches_to_rotator(monkeypatch):
    seen = _stub_registry(monkeypatch)
    assert cli.main(["myrot"]) == 0
    assert seen["store"] == "FAKE_CLIENT"


def test_run_subcommand_dispatches_to_rotator(monkeypatch):
    seen = _stub_registry(monkeypatch)
    assert cli.main(["run", "myrot"]) == 0
    assert seen["store"] == "FAKE_CLIENT"


def test_rotator_env_fallback(monkeypatch):
    seen = _stub_registry(monkeypatch)
    monkeypatch.setenv("ROTATOR", "myrot")
    assert cli.main([]) == 0
    assert seen["store"] == "FAKE_CLIENT"


# --- consumer subcommands ---


def test_fetch_prints_value(monkeypatch, capsys):
    monkeypatch.setattr(cli.fetch, "fetch_value", lambda s: "SECRETVALUE")
    assert cli.main(["fetch", "gitlab-pat"]) == 0
    assert capsys.readouterr().out.strip() == "SECRETVALUE"


def test_git_credential_get_emits_password(monkeypatch, capsys):
    monkeypatch.setattr(cli.gitcredential.fetch, "fetch_value", lambda s: "PAT")
    assert cli.main(["git-credential", "gitlab-pat", "get"]) == 0
    assert capsys.readouterr().out == "password=PAT\n"


def test_github_token_prints_minted_token(monkeypatch, capsys):
    monkeypatch.setattr(
        cli.github, "mint_token", lambda s, a, i, api: "ghs_tok"
    )
    rc = cli.main(
        ["github-token", "pem", "--app-id", "1", "--installation-id", "2"]
    )
    assert rc == 0
    assert capsys.readouterr().out.strip() == "ghs_tok"


def test_install_requires_user_in_token_mode(capsys):
    assert cli.main(["install", "some-uuid"]) == 2
    assert "--user" in capsys.readouterr().err


def test_install_github_requires_app_id(capsys):
    assert cli.main(["install", "pem", "--github"]) == 2
    assert "--app-id" in capsys.readouterr().err


def test_install_dry_run(monkeypatch, capsys, tmp_path):
    monkeypatch.setenv("ROTATO_CONFIG_DIR", str(tmp_path))
    rc = cli.main(["install", "some-uuid", "--user", "alice", "--dry-run"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "dry run" in out
    assert "alice" in out

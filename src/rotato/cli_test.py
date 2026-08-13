"""Tests for the rotato CLI dispatcher."""

import rotato.cli as cli

# --- rotator dispatch (server side) ---


def _stub_registry(monkeypatch):
    seen = {}
    monkeypatch.setattr(
        cli.rotators,
        "REGISTRY",
        {"myrot": lambda store: seen.update(store=store)},
    )
    monkeypatch.setattr(cli.bws, "BwsClient", lambda: "CLIENT")
    return seen


def test_legacy_bare_name_dispatches(monkeypatch):
    seen = _stub_registry(monkeypatch)
    assert cli.main(["myrot"]) == 0
    assert seen["store"] == "CLIENT"


def test_refresh_dispatches(monkeypatch):
    seen = _stub_registry(monkeypatch)
    assert cli.main(["refresh", "myrot"]) == 0
    assert seen["store"] == "CLIENT"


def test_refresh_env_fallback(monkeypatch):
    seen = _stub_registry(monkeypatch)
    monkeypatch.setenv("ROTATOR", "myrot")
    assert cli.main([]) == 0
    assert seen["store"] == "CLIENT"


def test_unknown_rotator_returns_2(capsys):
    assert cli.main(["definitely-not-a-rotator"]) == 2
    assert "unknown rotator" in capsys.readouterr().err


def test_refresh_no_name_returns_2(monkeypatch):
    monkeypatch.delenv("ROTATOR", raising=False)
    assert cli.main([]) == 2


# --- consumer subcommands ---


def test_print_outputs_credential(monkeypatch, capsys):
    monkeypatch.setattr(cli.credential, "usable_credential", lambda s: "SECRET")
    assert cli.main(["print", "gitlab-pat"]) == 0
    assert capsys.readouterr().out.strip() == "SECRET"


def test_install_github_requires_app_id(capsys):
    assert cli.main(["install", "some-uuid", "--github"]) == 2
    assert "--app-id" in capsys.readouterr().err


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


def test_list_rotators(monkeypatch, capsys):
    monkeypatch.setattr(
        cli.rotators, "REGISTRY", {"gitlab-pat": lambda s: None}
    )
    assert cli.main(["list", "rotators"]) == 0
    assert "gitlab-pat" in capsys.readouterr().out


def test_list_secrets(monkeypatch, capsys, tmp_path):
    monkeypatch.setenv("ROTATO_CONFIG_DIR", str(tmp_path))
    cli.config.record_secret("gl", cli.config.Entry(uuid="U"))
    assert cli.main(["list", "secrets"]) == 0
    out = capsys.readouterr().out
    assert "gl" in out
    assert "U" in out

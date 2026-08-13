import rotato.cli as cli
from rotato.cli import main

# --- legacy server-side path (container ENTRYPOINT ["rotato"]) ---


def test_unknown_rotator_returns_2(capsys):
    assert main(["definitely-not-a-rotator"]) == 2
    assert "unknown rotator" in capsys.readouterr().err


def test_no_name_returns_2(monkeypatch):
    monkeypatch.delenv("ROTATOR", raising=False)
    assert main([]) == 2


def test_run_subcommand_unknown_rotator_returns_2(capsys):
    assert main(["run", "nope"]) == 2
    assert "unknown rotator" in capsys.readouterr().err


# --- consumer subcommands ---


def test_fetch_prints_value(monkeypatch, capsys):
    monkeypatch.setattr(cli.fetch, "fetch_value", lambda s: "SECRETVALUE")
    assert main(["fetch", "gitlab-pat"]) == 0
    assert capsys.readouterr().out.strip() == "SECRETVALUE"


def test_git_credential_get_emits_password(monkeypatch, capsys):
    monkeypatch.setattr(cli.gitcredential.fetch, "fetch_value", lambda s: "PAT")
    assert main(["git-credential", "gitlab-pat", "get"]) == 0
    assert capsys.readouterr().out == "password=PAT\n"


def test_github_token_prints_minted_token(monkeypatch, capsys):
    monkeypatch.setattr(
        cli.github, "mint_token", lambda s, a, i, api: "ghs_tok"
    )
    rc = main(
        ["github-token", "pem", "--app-id", "1", "--installation-id", "2"]
    )
    assert rc == 0
    assert capsys.readouterr().out.strip() == "ghs_tok"


def test_install_requires_user_in_token_mode(capsys):
    assert main(["install", "some-uuid"]) == 2
    assert "--user" in capsys.readouterr().err


def test_install_github_requires_app_id(capsys):
    assert main(["install", "pem", "--github"]) == 2
    assert "--app-id" in capsys.readouterr().err


def test_install_dry_run(monkeypatch, capsys):
    monkeypatch.setenv("ROTATO_CONFIG_DIR", "/tmp/rotato-test-doesnotmatter")
    rc = main(["install", "some-uuid", "--user", "alice", "--dry-run"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "dry run" in out
    assert "alice" in out

"""rotato CLI.

One entry point (the `rotato` console script) with two surfaces:

  server    rotato run <name>            run a named rotator (Cloud Run job)
  consumer  rotato install ...           bootstrap this machine
            rotato fetch <name|uuid>     print a secret's value, read-only
            rotato github-token <...>    mint a GitHub App installation token
            rotato git-credential <...>  git credential helper

Backward-compatible: a bare `rotato <name>` (or the ROTATOR env var) with no
recognized subcommand still runs a rotator, so the container ENTRYPOINT keeps
working unchanged.
"""

import argparse
import os
import sys

from rotato import bws, rotators
from rotato.consumer import fetch, gitcredential, github, install

_SUBCOMMANDS = {"run", "fetch", "github-token", "git-credential", "install"}


def _run_rotator(name: str) -> int:
    if not name:
        print(
            "usage: rotato run <rotator-name>  (or set ROTATOR)",
            file=sys.stderr,
        )
        return 2
    run = rotators.REGISTRY.get(name)
    if run is None:
        print(f"unknown rotator: {name}", file=sys.stderr)
        return 2
    # Let failures propagate: the traceback (incl. any RotationError break-glass
    # value) goes to stderr -> Cloud Logging, and the non-zero exit trips the
    # failure alert.
    run(bws.BwsClient())
    return 0


def _cmd_run(args) -> int:
    return _run_rotator(args.name or os.environ.get("ROTATOR", ""))


def _cmd_fetch(args) -> int:
    print(fetch.fetch_value(args.secret))
    return 0


def _cmd_github_token(args) -> int:
    print(
        github.mint_token(
            args.secret, args.app_id, args.installation_id, args.api
        )
    )
    return 0


def _cmd_git_credential(args) -> int:
    sys.stdout.write(
        gitcredential.emit_credential(
            args.secret,
            args.operation,
            is_github=args.github,
            app_id=args.app_id,
            installation_id=args.installation_id,
            api=args.api,
        )
    )
    return 0


def _cmd_install(args) -> int:
    if args.github:
        if not args.app_id or not args.installation_id:
            print(
                "error: --app-id and --installation-id are required "
                "with --github",
                file=sys.stderr,
            )
            return 2
    elif not args.user:
        print("error: --user <git-user> is required", file=sys.stderr)
        return 2
    return install.run(
        install.InstallArgs(
            secret_id=args.secret,
            mode="github" if args.github else "token",
            host=args.host or "",
            user=args.user or "",
            app_id=args.app_id or "",
            installation_id=args.installation_id or "",
            name=args.name or "",
            git_file=args.file or "",
            dry_run=args.dry_run,
        )
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="rotato")
    sub = parser.add_subparsers(dest="command")

    p_run = sub.add_parser("run", help="run a named rotator (server-side)")
    p_run.add_argument("name", nargs="?", help="rotator name (or set ROTATOR)")
    p_run.set_defaults(func=_cmd_run)

    p_fetch = sub.add_parser("fetch", help="print a secret's value, read-only")
    p_fetch.add_argument("secret", help="secret name or uuid")
    p_fetch.set_defaults(func=_cmd_fetch)

    p_gh = sub.add_parser(
        "github-token", help="mint a GitHub App installation token"
    )
    p_gh.add_argument("secret", help="PEM secret name or uuid")
    p_gh.add_argument("--app-id", required=True, help="App ID or Client ID")
    p_gh.add_argument("--installation-id", required=True)
    p_gh.add_argument("--api", default=github.DEFAULT_API)
    p_gh.set_defaults(func=_cmd_github_token)

    p_gc = sub.add_parser("git-credential", help="git credential helper")
    p_gc.add_argument("secret", help="secret name or uuid")
    p_gc.add_argument(
        "operation", nargs="?", default="", help="get|store|erase"
    )
    p_gc.add_argument("--github", action="store_true", help="GitHub App mode")
    p_gc.add_argument("--app-id", default="")
    p_gc.add_argument("--installation-id", default="")
    p_gc.add_argument("--api", default=github.DEFAULT_API)
    p_gc.set_defaults(func=_cmd_git_credential)

    p_in = sub.add_parser("install", help="one-time per-machine consumer setup")
    p_in.add_argument("secret", help="secret uuid to install")
    p_in.add_argument("--github", action="store_true", help="GitHub App mode")
    p_in.add_argument("--host", help="git host (default gitlab/github.com)")
    p_in.add_argument("--user", help="git username (required, token mode)")
    p_in.add_argument("--app-id", help="App/Client ID (required --github)")
    p_in.add_argument(
        "--installation-id", help="installation ID (required --github)"
    )
    p_in.add_argument("--name", help="name to record (default: BWS key)")
    p_in.add_argument("--file", help="git config file (default: --global)")
    p_in.add_argument("--dry-run", action="store_true")
    p_in.set_defaults(func=_cmd_install)

    return parser


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)

    # Legacy: bare `rotato <name>` (or ROTATOR env) still runs a rotator, so the
    # container ENTRYPOINT ["rotato"] keeps working. Only fall through when the
    # first token is neither a known subcommand nor an option.
    legacy = not argv or (
        argv[0] not in _SUBCOMMANDS and not argv[0].startswith("-")
    )
    if legacy:
        return _run_rotator(argv[0] if argv else os.environ.get("ROTATOR", ""))

    args = _build_parser().parse_args(argv)
    return args.func(args)

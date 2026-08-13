"""rotato CLI.

One entry point (the `rotato` console script) with two surfaces:

  consumer  rotato install <uuid> …        register a secret on this machine
            rotato print <name|uuid>        print the usable credential
            rotato setup github|gitlab|git  wire git to an installed secret
            rotato list secrets|rotators    list installed secrets / rotators
  server    rotato refresh <name>           run a rotator (Cloud Run job)

Backward-compatible: a bare `rotato <name>` (or the ROTATOR env var) with no
recognized subcommand still runs a rotator, so the container ENTRYPOINT keeps
working unchanged.
"""

import argparse
import os
import sys

from rotato import bws, rotators
from rotato.consumer import config, credential, install, setup

_SUBCOMMANDS = {"install", "print", "setup", "list", "refresh"}


def _run_rotator(name: str) -> int:
    if not name:
        print(
            "usage: rotato refresh <rotator-name>  (or set ROTATOR)",
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


def _cmd_refresh(args) -> int:
    return _run_rotator(args.name or os.environ.get("ROTATOR", ""))


def _cmd_install(args) -> int:
    if args.github and (not args.app_id or not args.installation_id):
        print(
            "error: --app-id and --installation-id are required with --github",
            file=sys.stderr,
        )
        return 2
    return install.run(
        install.InstallArgs(
            uuid=args.uuid,
            name=args.name or "",
            github=args.github,
            app_id=args.app_id or "",
            installation_id=args.installation_id or "",
            dry_run=args.dry_run,
        )
    )


def _cmd_print(args) -> int:
    print(credential.usable_credential(args.secret))
    return 0


def _cmd_setup(args) -> int:
    return setup.run(
        setup.SetupArgs(
            target=args.target,
            name_or_uuid=args.secret,
            user=args.user or "",
            host=args.host or "",
            git_file=args.file or "",
            dry_run=args.dry_run,
        )
    )


def _cmd_list(args) -> int:
    if args.what == "rotators":
        for name in sorted(rotators.REGISTRY):
            print(name)
        return 0
    secrets = config.load_secrets()
    for name in sorted(secrets):
        entry = secrets[name]
        print(f"{name}\t{entry.kind}\t{entry.uuid}")
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="rotato")
    sub = parser.add_subparsers(dest="command")

    p_install = sub.add_parser(
        "install", help="register a secret on this machine"
    )
    p_install.add_argument("uuid", help="Bitwarden secret uuid")
    p_install.add_argument("--name", help="friendly name (default: BWS key)")
    p_install.add_argument(
        "--github", action="store_true", help="a GitHub App PEM (mints tokens)"
    )
    p_install.add_argument("--app-id", help="App/Client ID (required --github)")
    p_install.add_argument(
        "--installation-id", help="installation ID (required --github)"
    )
    p_install.add_argument("--dry-run", action="store_true")
    p_install.set_defaults(func=_cmd_install)

    p_print = sub.add_parser("print", help="print the usable credential")
    p_print.add_argument("secret", help="installed name or uuid")
    p_print.set_defaults(func=_cmd_print)

    p_setup = sub.add_parser("setup", help="wire git to an installed secret")
    p_setup.add_argument("target", choices=["github", "gitlab", "git"])
    p_setup.add_argument("secret", help="installed name or uuid")
    p_setup.add_argument("--user", help="git username (required, gitlab/git)")
    p_setup.add_argument("--host", help="git host (required for 'git')")
    p_setup.add_argument("--file", help="git config file (default: --global)")
    p_setup.add_argument("--dry-run", action="store_true")
    p_setup.set_defaults(func=_cmd_setup)

    p_list = sub.add_parser("list", help="list installed secrets / rotators")
    p_list.add_argument("what", choices=["secrets", "rotators"])
    p_list.set_defaults(func=_cmd_list)

    p_refresh = sub.add_parser("refresh", help="run a rotator (server-side)")
    p_refresh.add_argument("name", nargs="?", help="rotator name (or ROTATOR)")
    p_refresh.set_defaults(func=_cmd_refresh)

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

"""rotato CLI.

One entry point (the `rotato` console script) with two surfaces:

  consumer  rotato install <uuid> …          register a secret on this machine
            rotato print <name|uuid>          print the usable credential
            rotato setup github|gitlab|git    wire git to an installed secret
            rotato list secrets|rotators|tags  list installed / supported things
  server    rotato refresh                    rotate every tagged secret (job)

The server side is tag-driven: `refresh` scans the whole Bitwarden project and
rotates each secret whose note enrolls it (`#rotato=<type>`). A bare `rotato`
(the container ENTRYPOINT with no args) does the same, so no per-secret config
is baked into the job.
"""

import argparse
import datetime
import os
import sys

from rotato import bws, roster, rotators, tags
from rotato.consumer import config, credential, install, setup

_SUBCOMMANDS = {"install", "print", "setup", "list", "refresh"}


def _refresh_batch() -> int:
    org = os.environ.get("BWS_ORGANIZATION_ID", "")
    if not org:
        print(
            "error: BWS_ORGANIZATION_ID is required to rotate", file=sys.stderr
        )
        return 2
    stale_after = float(
        os.environ.get("STALE_AFTER_DAYS", roster.DEFAULT_STALE_AFTER_DAYS)
    )
    client = bws.BwsClient()
    secrets = client.list_secrets(org)
    now = datetime.datetime.now(datetime.UTC)
    report = roster.rotate_tagged(client, secrets, now, stale_after)
    return roster.render(report)


def _cmd_refresh(args) -> int:
    del args  # refresh takes no options; batch config comes from the env
    return _refresh_batch()


def _cmd_install(args) -> int:
    if args.github and (not args.app_id or not args.installation_id):
        print(
            "error: --app-id and --installation-id are required with --github",
            file=sys.stderr,
        )
        return 2
    if (args.app_id or args.installation_id) and not args.github:
        print(
            "error: --app-id/--installation-id only apply with --github; "
            "add --github to install a GitHub App (they are ignored for a "
            "plain token)",
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


def _print_tags() -> None:
    """Document the note-tag grammar and each rotator's config knobs."""
    print(f"#{tags.ENROLL}=<type>\trequired; enroll for rotation (type below)")
    print(
        f"#{roster.CADENCE_TAG}=<days>\toptional; max age before a STALE alert "
        f"(default {int(roster.DEFAULT_STALE_AFTER_DAYS)})"
    )
    for name in sorted(rotators.REGISTRY):
        rotator = rotators.REGISTRY[name]
        print(f"\n{name}: {rotator.help}")
        for knob in rotator.knobs:
            print(f"  #{knob.name}=<v>\t{knob.help} (default {knob.default})")


def _cmd_list(args) -> int:
    if args.what == "rotators":
        for name in sorted(rotators.REGISTRY):
            print(f"{name}\t{rotators.REGISTRY[name].help}")
        return 0
    if args.what == "tags":
        _print_tags()
        return 0
    secrets = config.load_secrets()
    for name in sorted(secrets):
        entry = secrets[name]
        print(f"{name}\t{entry.kind}\t{entry.uuid}")
    return 0


def _complete_secrets(prefix, **_kwargs):
    """Tab-complete installed secret names (never their values)."""
    return [name for name in config.load_secrets() if name.startswith(prefix)]


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
    p_print.add_argument(
        "secret", help="installed name or uuid"
    ).completer = _complete_secrets
    p_print.set_defaults(func=_cmd_print)

    p_setup = sub.add_parser("setup", help="wire git to an installed secret")
    p_setup.add_argument("target", choices=["github", "gitlab", "git"])
    p_setup.add_argument(
        "secret", help="installed name or uuid"
    ).completer = _complete_secrets
    p_setup.add_argument("--user", help="git username (required, gitlab/git)")
    p_setup.add_argument("--host", help="git host (required for 'git')")
    p_setup.add_argument("--file", help="git config file (default: --global)")
    p_setup.add_argument("--dry-run", action="store_true")
    p_setup.set_defaults(func=_cmd_setup)

    p_list = sub.add_parser("list", help="list installed / supported things")
    p_list.add_argument("what", choices=["secrets", "rotators", "tags"])
    p_list.set_defaults(func=_cmd_list)

    p_refresh = sub.add_parser(
        "refresh", help="rotate every tagged secret (server-side)"
    )
    p_refresh.set_defaults(func=_cmd_refresh)

    return parser


def main(argv=None) -> int:
    parser = _build_parser()

    # Shell completion (argcomplete). Imported and invoked only while actually
    # completing, so normal runs and the server-side refresh don't pay for it.
    # Activate with: eval "$(register-python-argcomplete rotato)"
    if os.environ.get("_ARGCOMPLETE"):
        import argcomplete  # pylint: disable=import-outside-toplevel

        argcomplete.autocomplete(parser)

    argv = list(sys.argv[1:] if argv is None else argv)

    # A bare `rotato` (the container ENTRYPOINT with no args) rotates every
    # tagged secret, so the Cloud Run job needs no per-secret arguments. Only
    # fall through when the first token is neither a subcommand nor an option.
    legacy = not argv or (
        argv[0] not in _SUBCOMMANDS and not argv[0].startswith("-")
    )
    if legacy:
        return _refresh_batch()

    args = parser.parse_args(argv)
    return args.func(args)

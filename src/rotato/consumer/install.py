"""`rotato install` — register a secret on this machine.

Records a name -> entry in secrets.json so the secret can be used locally
(`rotato print <name>`, `rotato setup … <name>`). Ensures this machine's
read-only Bitwarden token exists (prompts on first run, kept thereafter).
No git, no `--user` — wiring a tool to a secret is `rotato setup`.

Two kinds:
  token   (default)  the stored value is the credential (e.g. a GitLab PAT).
  --github           the stored value is a GitHub App private key (PEM); a
                     short-lived installation token is minted from it on use.
                     Needs --app-id and --installation-id.
"""

import dataclasses
import getpass
import os
import sys

from rotato import bws
from rotato.consumer import config


@dataclasses.dataclass
class InstallArgs:
    uuid: str
    name: str = ""
    github: bool = False
    app_id: str = ""
    installation_id: str = ""
    dry_run: bool = False


def _ensure_token() -> None:
    """Store this machine's read-only BWS token, prompting only if missing."""
    token_file = config.token_file()
    if token_file.exists() and token_file.stat().st_size > 0:
        print(f"token already present at {token_file} — keeping it")
        return
    token_file.parent.mkdir(parents=True, exist_ok=True)
    token = getpass.getpass("Paste this machine's READ-ONLY BWS token: ")
    # 0600 from creation, and fchmod to tighten a pre-existing (e.g. empty,
    # world-readable) file we're about to overwrite — os.open's mode only
    # applies on create.
    fd = os.open(token_file, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as fobj:
        os.fchmod(fobj.fileno(), 0o600)
        fobj.write(token)
    print(f"wrote {token_file} (chmod 600)")


def _default_name(uuid: str) -> str:
    """The secret's own key in Bitwarden; best-effort (net/auth may fail)."""
    try:
        return bws.BwsClient(access_token=config.read_token()).get(uuid).key
    except Exception:  # pylint: disable=broad-exception-caught
        # A label lookup must never fail the install.
        return ""


def run(args: InstallArgs) -> int:
    kind = config.KIND_GITHUB_APP if args.github else config.KIND_TOKEN
    name = args.name or "<name from Bitwarden>"

    print("This will:")
    print(
        f"  1. ensure this machine's read-only token -> {config.token_file()}"
    )
    print(f"  2. record {name} -> {args.uuid} (kind: {kind})")
    print(f"     in {config.secrets_file()}")
    print()

    if args.dry_run:
        print("(dry run — nothing changed)")
        return 0

    _ensure_token()

    name = args.name or _default_name(args.uuid)
    if not name:
        print(
            "error: could not read the secret's name from Bitwarden; "
            "rerun with --name <name>",
            file=sys.stderr,
        )
        return 1

    entry = config.Entry(
        uuid=args.uuid,
        kind=kind,
        app_id=args.app_id,
        installation_id=args.installation_id,
    )
    config.record_secret(name, entry)
    print(f"installed '{name}' -> {args.uuid} (kind: {kind})")
    print()
    print(f"use it:   rotato print {name}")
    if kind == config.KIND_GITHUB_APP:
        print(f"wire git: rotato setup github {name}")
    else:
        print(f"wire git: rotato setup gitlab {name} --user <git-user>")
    return 0

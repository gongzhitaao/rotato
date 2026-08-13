"""`rotato install` — one-time per-machine consumer setup.

Wires git to fetch the current credential from Bitwarden on demand. Unlike the
old bash bootstrap it copies nothing: with `rotato` already on PATH (e.g. from
`uv tool install rotato`) it only writes this machine's read-only BWS token, the
name -> uuid record, and the git credential-helper config. No repo checkout.

Two modes:
  token   (default)  <uuid> is a token in Bitwarden (e.g. a GitLab PAT).
  --github           <uuid> is a GitHub App private key (PEM); git gets a
                     short-lived installation token minted from it. Needs
                     --app-id and --installation-id; --user is not used.
"""

import dataclasses
import getpass
import os
import shutil
import subprocess
import sys

from rotato import bws
from rotato.consumer import config


@dataclasses.dataclass
class InstallArgs:
    secret_id: str
    mode: str = "token"  # "token" or "github"
    host: str = ""
    user: str = ""
    app_id: str = ""
    installation_id: str = ""
    name: str = ""
    git_file: str = ""  # empty -> git --global
    dry_run: bool = False


def _rotato_bin() -> str:
    """Absolute path to this rotato entry point.

    Embedded into the git credential-helper command so it resolves even when git
    runs with a minimal PATH.
    """
    return shutil.which("rotato") or os.path.realpath(sys.argv[0])


def _helper_cmd(args: InstallArgs, rotato: str) -> str:
    if args.mode == "github":
        return (
            f"!{rotato} git-credential --github "
            f"--app-id {args.app_id} --installation-id {args.installation_id} "
            f"{args.secret_id}"
        )
    return f"!{rotato} git-credential {args.secret_id}"


def _git_config(args: InstallArgs) -> list[str]:
    if args.git_file:
        return ["git", "config", "--file", args.git_file]
    return ["git", "config", "--global"]


def _default_name(args: InstallArgs) -> str:
    """The secret's own key in Bitwarden; best-effort (net/auth may fail)."""
    try:
        client = bws.BwsClient(access_token=config.read_token())
        return client.get(args.secret_id).key
    except Exception:  # pylint: disable=broad-exception-caught
        # A label lookup must never fail the install.
        return ""


def run(args: InstallArgs) -> int:
    default_host = "github.com" if args.mode == "github" else "gitlab.com"
    host = args.host or default_host
    rotato = _rotato_bin()
    helper = _helper_cmd(args, rotato)
    git_dest = args.git_file or "git --global (~/.gitconfig)"

    recorded_name = args.name or "<name from Bitwarden>"
    print("This will:")
    print(f"  1. store this machine's read-only token -> {config.token_file()}")
    print(f"  2. set in {git_dest}:")
    if args.mode == "token":
        print(f"       credential.https://{host}.username = {args.user}")
    print(f"       credential.https://{host}.helper   = {helper}")
    print(
        f"  3. record {recorded_name} -> "
        f"{args.secret_id} in {config.secrets_file()}"
    )
    print()

    if args.dry_run:
        print("(dry run — nothing changed)")
        return 0

    # 1. token (prompt only if not already present).
    token_file = config.token_file()
    if token_file.exists() and token_file.stat().st_size > 0:
        print(f"token file already present at {token_file} — keeping it")
    else:
        token_file.parent.mkdir(parents=True, exist_ok=True)
        token = getpass.getpass("Paste this machine's READ-ONLY BWS token: ")
        # Write with 0600 from the start; never widen an existing file.
        fd = os.open(token_file, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as fobj:
            fobj.write(token)
        print(f"wrote {token_file} (chmod 600)")

    # 2. git config. --replace-all so re-runs (or an existing multi-valued
    # helper, e.g. from `gh auth setup-git`) collapse to our single value.
    git_cfg = _git_config(args)
    if args.mode == "token":
        key = f"credential.https://{host}.username"
        subprocess.run([*git_cfg, "--replace-all", key, args.user], check=True)
    key = f"credential.https://{host}.helper"
    subprocess.run([*git_cfg, "--replace-all", key, helper], check=True)
    print(f"configured git credential helper for https://{host}")

    # 3. record name -> uuid so ad-hoc auth can resolve a secret by name.
    name = args.name or _default_name(args)
    if name:
        config.record_secret(name, args.secret_id)
        print(f"recorded '{name}' -> {args.secret_id}")
    else:
        print(
            "warning: no --name given and could not read the secret's name "
            "from Bitwarden; skipping secrets.json (rerun with --name)",
            file=sys.stderr,
        )

    print()
    if args.mode == "github":
        print(
            f"done. test with:  rotato github-token {args.secret_id} "
            "| head -c 6; echo ..."
        )
    else:
        print(
            f"done. test with:  rotato fetch {args.secret_id} "
            "| head -c 6; echo ..."
        )
    print(f"then a real op:   git -C <a-{host}-repo> ls-remote")
    return 0

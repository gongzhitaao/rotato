"""`rotato setup github|gitlab|git` — wire git to an installed secret.

Writes a git credential helper that shells out to `rotato print <name>` on
`get`. The three targets differ only in host default and username:

  github  host github.com; username x-access-token (App installation token)
  gitlab  host gitlab.com; --user required (token)
  git     any host (--host required); --user required (token)

The secret must already be installed (`rotato install`); `setup` references it
by name, so rotations and re-mints happen transparently on every git op.
"""

import dataclasses
import os
import shlex
import shutil
import subprocess
import sys

from rotato.consumer import config


@dataclasses.dataclass
class SetupArgs:
    target: str  # "github" | "gitlab" | "git"
    name_or_uuid: str
    user: str = ""
    host: str = ""
    git_file: str = ""  # empty -> git --global
    dry_run: bool = False


def _rotato_bin() -> str:
    """Absolute path to this rotato entry point (git's PATH may be minimal)."""
    return shutil.which("rotato") or os.path.realpath(sys.argv[0])


def _git_config(git_file: str) -> list[str]:
    if git_file:
        return ["git", "config", "--file", git_file]
    return ["git", "config", "--global"]


def _helper(rotato: str, name: str, is_github: bool) -> str:
    # git runs a "!"-helper via the shell with the operation ($1) appended, so
    # only act on `get`. shlex.quote the path/name (git's PATH may be minimal).
    inner = f"{shlex.quote(rotato)} print {shlex.quote(name)}"
    fmt = (
        "'username=x-access-token\\npassword=%s\\n'"
        if is_github
        else "'password=%s\\n'"
    )
    return f'!f() {{ test "$1" = get && printf {fmt} "$({inner})"; }}; f'


def run(args: SetupArgs) -> int:
    name, entry = config.resolve(args.name_or_uuid)  # errors if not installed
    is_github = args.target == "github"

    if is_github:
        host = args.host or "github.com"
        if entry.kind != config.KIND_GITHUB_APP:
            print(
                f"error: 'setup github' needs a --github secret; '{name}' is "
                f"kind '{entry.kind}' — use 'setup gitlab' or 'setup git'",
                file=sys.stderr,
            )
            return 2
    else:
        host = args.host or ("gitlab.com" if args.target == "gitlab" else "")
        if not host:
            print("error: --host is required for 'setup git'", file=sys.stderr)
            return 2
        if not args.user:
            print(
                f"error: --user is required for 'setup {args.target}'",
                file=sys.stderr,
            )
            return 2
        if entry.kind != config.KIND_TOKEN:
            print(
                f"error: 'setup {args.target}' needs a token secret; '{name}' "
                f"is kind '{entry.kind}' — use 'setup github'",
                file=sys.stderr,
            )
            return 2

    rotato = _rotato_bin()
    helper = _helper(rotato, name, is_github)
    git_dest = args.git_file or "git --global (~/.gitconfig)"

    print(f"This will set in {git_dest}:")
    if not is_github:
        print(f"  credential.https://{host}.username = {args.user}")
    print(f"  credential.https://{host}.helper   = {helper}")
    print()
    if args.dry_run:
        print("(dry run — nothing changed)")
        return 0

    git_cfg = _git_config(args.git_file)
    if not is_github:
        subprocess.run(
            [
                *git_cfg,
                "--replace-all",
                f"credential.https://{host}.username",
                args.user,
            ],
            check=True,
        )
    subprocess.run(
        [
            *git_cfg,
            "--replace-all",
            f"credential.https://{host}.helper",
            helper,
        ],
        check=True,
    )
    print(f"configured https://{host} to use 'rotato print {name}'")
    return 0

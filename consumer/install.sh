#!/usr/bin/env bash
# One-time per-machine setup so git fetches the current rotated PAT from
# Bitwarden. Run once on each consumer machine (laptop, VM).
#
# Usage:
#   consumer/install.sh <secret-uuid> --user <git-user> [options]
#
# Options:
#   --host <host>       git host to configure          (default: gitlab.com)
#   --user <user>       username for that host          (required)
#   --bin  <dir>        where to install the scripts    (default: ~/.local/bin)
#   --file <path>       git config file to write to     (default: git --global)
#   --token-file <path> where to store this machine's read-only BWS token
#                                                       (default: ~/.config/rotato/token)
#   --dry-run           print exactly what would change, then stop
set -euo pipefail

HERE="$(dirname "$(readlink -f "$0")")"

HOST="gitlab.com"
GIT_USER=""
BIN="$HOME/.local/bin"
GIT_FILE=""
TOKEN_FILE="$HOME/.config/rotato/token"
DRY=0
SECRET_ID=""

while [ $# -gt 0 ]; do
  case "$1" in
    --host) HOST="$2"; shift 2 ;;
    --user) GIT_USER="$2"; shift 2 ;;
    --bin) BIN="$2"; shift 2 ;;
    --file) GIT_FILE="$2"; shift 2 ;;
    --token-file) TOKEN_FILE="$2"; shift 2 ;;
    --dry-run) DRY=1; shift ;;
    -*) echo "unknown option: $1" >&2; exit 2 ;;
    *) SECRET_ID="$1"; shift ;;
  esac
done

[ -n "$SECRET_ID" ] || {
  echo "usage: install.sh <secret-uuid> --user <git-user> [options]" >&2
  exit 2
}
[ -n "$GIT_USER" ] || { echo "error: --user <git-user> is required" >&2; exit 2; }

if [ -n "$GIT_FILE" ]; then
  git_cfg=(git config --file "$GIT_FILE")
  git_dest="$GIT_FILE"
else
  git_cfg=(git config --global)
  git_dest="git --global (~/.gitconfig or ~/.config/git/config)"
fi

helper_cmd="!$BIN/rotato-git-credential $SECRET_ID"

echo "This will:"
echo "  1. check bws + jq + git are installed"
echo "  2. store this machine's read-only BWS token -> $TOKEN_FILE (chmod 600)"
echo "  3. install rotato-fetch + rotato-git-credential -> $BIN"
echo "  4. set in $git_dest:"
echo "       credential.https://$HOST.username = $GIT_USER"
echo "       credential.https://$HOST.helper   = $helper_cmd"
echo

[ "$DRY" = 1 ] && { echo "(dry run — nothing changed)"; exit 0; }

# 1. deps
for tool in bws jq git; do
  command -v "$tool" >/dev/null || {
    echo "error: '$tool' not found on PATH" >&2
    exit 1
  }
done

# 2. token (prompt only if not already present)
if [ -s "$TOKEN_FILE" ]; then
  echo "token file already present at $TOKEN_FILE — keeping it"
else
  mkdir -p "$(dirname "$TOKEN_FILE")"
  printf "Paste this machine's READ-ONLY BWS access token: "
  read -rs token; echo
  ( umask 077; printf '%s' "$token" > "$TOKEN_FILE" )
  unset token
  echo "wrote $TOKEN_FILE (chmod 600)"
fi

# 3. scripts
mkdir -p "$BIN"
install -m 755 "$HERE/rotato-fetch" "$BIN/rotato-fetch"
install -m 755 "$HERE/rotato-git-credential" "$BIN/rotato-git-credential"
echo "installed rotato-fetch + rotato-git-credential -> $BIN"

# 4. git config
"${git_cfg[@]}" "credential.https://$HOST.username" "$GIT_USER"
"${git_cfg[@]}" "credential.https://$HOST.helper" "$helper_cmd"
echo "configured git credential helper for https://$HOST"

echo
echo "done. test with:  rotato-fetch $SECRET_ID | head -c 6; echo ..."
echo "then a real op:   git -C <a-$HOST-repo> ls-remote"

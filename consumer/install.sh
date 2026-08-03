#!/usr/bin/env bash
# One-time per-machine setup so git fetches the current credential from
# Bitwarden. Run once on each consumer machine (laptop, VM).
#
# Two modes:
#   token   (default) <secret-uuid> is a token in Bitwarden (e.g. a GitLab PAT).
#   --github          <secret-uuid> is a GitHub App private key (PEM); git gets
#                     a short-lived installation token minted from it. Needs
#                     --app-id and --installation-id; --user is not used.
#
# Usage:
#   consumer/install.sh <secret-uuid> --user <git-user> [options]
#   consumer/install.sh <pem-uuid> --github --app-id <id> --installation-id <id> [options]
#
# Options:
#   --host <host>       git host to configure   (default: gitlab.com; github.com in --github)
#   --user <user>       username for that host           (required in token mode)
#   --github            GitHub App mode (mint installation tokens from a PEM)
#   --app-id <id>       GitHub App ID or Client ID       (required with --github)
#   --installation-id <id>  GitHub App installation ID   (required with --github)
#   --bin  <dir>        where to install the scripts    (default: ~/.local/bin)
#   --file <path>       git config file to write to     (default: git --global)
#   --token-file <path> where to store this machine's read-only BWS token
#                                                       (default: ~/.config/rotato/token)
#   --dry-run           print exactly what would change, then stop
set -euo pipefail

HERE="$(dirname "$(readlink -f "$0")")"

HOST=""
GIT_USER=""
MODE="token"
APP_ID=""
INSTALL_ID=""
BIN="$HOME/.local/bin"
GIT_FILE=""
TOKEN_FILE="$HOME/.config/rotato/token"
DRY=0
SECRET_ID=""

while [ $# -gt 0 ]; do
  case "$1" in
    --host) HOST="$2"; shift 2 ;;
    --user) GIT_USER="$2"; shift 2 ;;
    --github) MODE="github"; shift ;;
    --app-id) APP_ID="$2"; shift 2 ;;
    --installation-id) INSTALL_ID="$2"; shift 2 ;;
    --bin) BIN="$2"; shift 2 ;;
    --file) GIT_FILE="$2"; shift 2 ;;
    --token-file) TOKEN_FILE="$2"; shift 2 ;;
    --dry-run) DRY=1; shift ;;
    -*) echo "unknown option: $1" >&2; exit 2 ;;
    *) SECRET_ID="$1"; shift ;;
  esac
done

# Host default depends on mode; explicit --host always wins.
[ -n "$HOST" ] || { [ "$MODE" = "github" ] && HOST="github.com" || HOST="gitlab.com"; }

[ -n "$SECRET_ID" ] || {
  echo "usage: install.sh <secret-uuid> --user <git-user> [options]" >&2
  exit 2
}
if [ "$MODE" = "github" ]; then
  [ -n "$APP_ID" ] || { echo "error: --app-id is required with --github" >&2; exit 2; }
  [ -n "$INSTALL_ID" ] || { echo "error: --installation-id is required with --github" >&2; exit 2; }
else
  [ -n "$GIT_USER" ] || { echo "error: --user <git-user> is required" >&2; exit 2; }
fi

if [ -n "$GIT_FILE" ]; then
  git_cfg=(git config --file "$GIT_FILE")
  git_dest="$GIT_FILE"
else
  git_cfg=(git config --global)
  git_dest="git --global (~/.gitconfig or ~/.config/git/config)"
fi

if [ "$MODE" = "github" ]; then
  helper_cmd="!ROTATO_GH_APP_ID=$APP_ID ROTATO_GH_INSTALLATION_ID=$INSTALL_ID $BIN/rotato-git-credential --github $SECRET_ID"
else
  helper_cmd="!$BIN/rotato-git-credential $SECRET_ID"
fi

if [ "$MODE" = "github" ]; then
  deps_line="bws + jq + git + openssl + curl"
  scripts_line="rotato-fetch + rotato-git-credential + rotato-github-token"
else
  deps_line="bws + jq + git"
  scripts_line="rotato-fetch + rotato-git-credential"
fi

echo "This will:"
echo "  1. check $deps_line are installed"
echo "  2. store this machine's read-only BWS token -> $TOKEN_FILE (chmod 600)"
echo "  3. install $scripts_line -> $BIN"
echo "  4. set in $git_dest:"
if [ "$MODE" = "token" ]; then
  echo "       credential.https://$HOST.username = $GIT_USER"
fi
echo "       credential.https://$HOST.helper   = $helper_cmd"
echo

[ "$DRY" = 1 ] && { echo "(dry run — nothing changed)"; exit 0; }

# 1. deps
deps=(bws jq git)
[ "$MODE" = "github" ] && deps+=(openssl curl)
for tool in "${deps[@]}"; do
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
[ "$MODE" = "github" ] && install -m 755 "$HERE/rotato-github-token" "$BIN/rotato-github-token"
echo "installed $scripts_line -> $BIN"

# 4. git config. --replace-all so re-runs (or an existing multi-valued helper,
# e.g. from `gh auth setup-git`) collapse to exactly our single value.
if [ "$MODE" = "token" ]; then
  "${git_cfg[@]}" --replace-all "credential.https://$HOST.username" "$GIT_USER"
fi
"${git_cfg[@]}" --replace-all "credential.https://$HOST.helper" "$helper_cmd"
echo "configured git credential helper for https://$HOST"

echo
if [ "$MODE" = "github" ]; then
  echo "done. test with:  ROTATO_GH_APP_ID=$APP_ID ROTATO_GH_INSTALLATION_ID=$INSTALL_ID rotato-github-token $SECRET_ID | head -c 6; echo ..."
else
  echo "done. test with:  rotato-fetch $SECRET_ID | head -c 6; echo ..."
fi
echo "then a real op:   git -C <a-$HOST-repo> ls-remote"

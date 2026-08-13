"""`rotato git-credential` — a git credential helper.

Git invokes a helper as `<helper> get|store|erase`, reading key=value context
on stdin and, on `get`, expecting `username=`/`password=` back on stdout. This
is a thin adapter over fetch / github-token; store and erase are no-ops (nothing
lives on disk). `install` wires it into git config for you, e.g.:

  [credential "https://gitlab.com"]
      username = <user>
      helper = "!rotato git-credential <name|uuid>"
  [credential "https://github.com"]
      helper = "!rotato git-credential --github
                --app-id .. --installation-id .. <pem>"
"""

from . import fetch, github


def emit_credential(
    name_or_uuid: str,
    operation: str,
    *,
    is_github: bool = False,
    app_id: str = "",
    installation_id: str = "",
    api: str = github.DEFAULT_API,
) -> str:
    """Return the git-credential response for `operation` (empty unless get)."""
    # git only needs a value on `get`; nothing to persist or clear otherwise.
    if operation != "get":
        return ""

    if is_github:
        # Installation tokens require the username x-access-token.
        token = github.mint_token(name_or_uuid, app_id, installation_id, api)
        return f"username=x-access-token\npassword={token}\n"
    return f"password={fetch.fetch_value(name_or_uuid)}\n"

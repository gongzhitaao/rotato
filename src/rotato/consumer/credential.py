"""`rotato print` — emit the usable credential for an installed secret.

Resolves a name or uuid against the installed registry (errors if not
installed) and returns the credential you would actually use:

  kind "token"       -> the stored value (e.g. a PAT), verbatim
  kind "github-app"  -> a freshly minted GitHub App installation token

This is the single fetch primitive; `setup` wires git to call it, and it is
also usable directly for env vars, app config, CI, etc.
"""

from rotato import bws
from rotato.consumer import config, github


def _raw_value(uuid: str) -> str:
    """The stored value of a Bitwarden secret, read-only, by uuid."""
    return bws.BwsClient(access_token=config.read_token()).get_value(uuid)


def _protocol_safe(value: str) -> str:
    """Refuse a value that would corrupt git's line-oriented credential wire.

    A newline/carriage-return/NUL lets the rest of the value be reparsed by git
    as attribute lines — refuse rather than emit a truncated or attacker-shaped
    credential.
    """
    if any(c in value for c in ("\n", "\r", "\0")):
        raise SystemExit(
            "rotato: credential contains a control character; refusing to emit "
            "it (would corrupt the git credential protocol)"
        )
    return value


def usable_credential(name_or_uuid: str) -> str:
    """The credential to use for an installed secret (mints for App entries)."""
    _, entry = config.resolve(name_or_uuid)
    if entry.kind == config.KIND_GITHUB_APP:
        pem = _raw_value(entry.uuid)
        return _protocol_safe(
            github.mint_token(pem, entry.app_id, entry.installation_id)
        )
    return _protocol_safe(_raw_value(entry.uuid))

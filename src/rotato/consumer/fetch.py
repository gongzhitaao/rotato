"""`rotato fetch <name|uuid>` — print a secret's current value, read-only.

The primitive every consumer builds on (git via `rotato git-credential`,
anything else — env vars, app config, systemd units — by calling this directly).
Authenticates with this machine's read-only BWS token and resolves a friendly
name to its uuid via secrets.json.
"""

from ..bws import BwsClient
from . import config


def fetch_value(name_or_uuid: str) -> str:
    secret_id = config.resolve(name_or_uuid)
    return BwsClient(access_token=config.read_token()).get_value(secret_id)

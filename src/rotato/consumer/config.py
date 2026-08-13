"""Consumer-side paths and the local name -> uuid registry.

State lives under ~/.config/rotato/ (override the whole dir with
ROTATO_CONFIG_DIR, or a single file with ROTATO_TOKEN_FILE /
ROTATO_SECRETS_FILE) — never in a repo checkout:

  token         this machine's read-only BWS access token (chmod 600)
  secrets.json  a JSON object mapping friendly name -> secret uuid, so a secret
                can be addressed by name instead of a uuid
"""

import json
import os
import pathlib
import re

# Bitwarden secret ids are UUIDs; anything else is treated as a friendly name.
_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


def config_dir() -> pathlib.Path:
    override = os.environ.get("ROTATO_CONFIG_DIR")
    if override:
        return pathlib.Path(override)
    return pathlib.Path.home() / ".config" / "rotato"


def token_file() -> pathlib.Path:
    override = os.environ.get("ROTATO_TOKEN_FILE")
    return pathlib.Path(override) if override else config_dir() / "token"


def secrets_file() -> pathlib.Path:
    override = os.environ.get("ROTATO_SECRETS_FILE")
    if override:
        return pathlib.Path(override)
    return config_dir() / "secrets.json"


def read_token() -> str:
    """This machine's read-only BWS access token; raises if missing/empty."""
    path = token_file()
    try:
        token = path.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise SystemExit(f"rotato: cannot read token file: {path}") from exc
    if not token:
        raise SystemExit(f"rotato: token file is empty: {path}")
    return token


def load_secrets() -> dict[str, str]:
    """The name -> uuid map; an empty dict if absent or unparseable."""
    try:
        data = json.loads(secrets_file().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def record_secret(name: str, uuid: str) -> None:
    """Record name -> uuid, replacing any existing entry for that name.

    Writes via a temp file in the same dir so the swap is atomic.
    """
    path = secrets_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    secrets = load_secrets()
    secrets[name] = uuid
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(
        json.dumps(secrets, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    tmp.replace(path)


def resolve(name_or_uuid: str) -> str:
    """Map a friendly name to its uuid; pass a uuid through unchanged.

    A recorded name wins over the uuid shape, so a name that happens to look
    like a uuid still resolves to its mapped value.
    """
    secrets = load_secrets()
    if name_or_uuid in secrets:
        return secrets[name_or_uuid]
    if _UUID_RE.match(name_or_uuid):
        return name_or_uuid
    raise SystemExit(
        f"rotato: unknown secret name {name_or_uuid!r}; "
        f"not found in {secrets_file()}"
    )

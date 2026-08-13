"""Consumer-side paths and the local installed-secret registry.

State lives under ~/.config/rotato/ (override the whole dir with
ROTATO_CONFIG_DIR, or a single file with ROTATO_TOKEN_FILE /
ROTATO_SECRETS_FILE) — never in a repo checkout:

  token         this machine's read-only BWS access token (chmod 600)
  secrets.json  installed entries: name -> {uuid, kind, ...}. `kind` is
                "token" (the stored value is the credential) or "github-app"
                (the stored value is a PEM; a token is minted from it).
"""

import dataclasses
import json
import os
import pathlib

KIND_TOKEN = "token"
KIND_GITHUB_APP = "github-app"


@dataclasses.dataclass
class Entry:
    """An installed secret and how to turn it into a usable credential."""

    uuid: str
    kind: str = KIND_TOKEN
    app_id: str = ""
    installation_id: str = ""

    @classmethod
    def from_json(cls, value) -> "Entry":
        # Legacy 0.1.x format was a bare uuid string; read it as a token entry.
        if isinstance(value, str):
            return cls(uuid=value, kind=KIND_TOKEN)
        return cls(
            uuid=value["uuid"],
            kind=value.get("kind", KIND_TOKEN),
            app_id=value.get("app_id", ""),
            installation_id=value.get("installation_id", ""),
        )

    def to_json(self) -> dict:
        data = {"uuid": self.uuid, "kind": self.kind}
        if self.kind == KIND_GITHUB_APP:
            data["app_id"] = self.app_id
            data["installation_id"] = self.installation_id
        return data


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


def load_secrets() -> dict[str, Entry]:
    """Installed entries by name; an empty dict if absent or unparseable."""
    try:
        data = json.loads(secrets_file().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(data, dict):
        return {}
    entries = {}
    for name, value in data.items():
        try:
            entries[name] = Entry.from_json(value)
        except (KeyError, TypeError, AttributeError):
            continue  # skip a malformed entry rather than fail the whole file
    return entries


def record_secret(name: str, entry: Entry) -> None:
    """Record name -> entry, replacing any existing entry for that name.

    Writes via a temp file in the same dir so the swap is atomic.
    """
    path = secrets_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    secrets = load_secrets()
    secrets[name] = entry
    payload = {n: e.to_json() for n, e in secrets.items()}
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    tmp.replace(path)


def resolve(name_or_uuid: str) -> tuple[str, Entry]:
    """Look up an installed entry by name or uuid.

    Returns (name, entry). Raises SystemExit if the identifier isn't installed
    — secrets.json is the allowlist; install a secret before using it.
    """
    secrets = load_secrets()
    if name_or_uuid in secrets:
        return name_or_uuid, secrets[name_or_uuid]
    for name, entry in secrets.items():
        if entry.uuid == name_or_uuid:
            return name, entry
    raise SystemExit(
        f"rotato: {name_or_uuid!r} is not installed; "
        f"run 'rotato install' first (see {secrets_file()})"
    )

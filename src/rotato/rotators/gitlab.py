"""Rotator: GitLab personal access token (self-rotation).

Config tags (in the secret's note): ``#host`` (GitLab instance base URL,
default https://gitlab.com), ``#expiry`` (new token lifetime in days, default
30). The PAT needs `api` scope (or `self_rotate` on GitLab >= 17.7) or the
self-rotate endpoint returns 403.
"""

import datetime

import httpx2

from rotato.rotators import base

_DEFAULT_HOST = "https://gitlab.com"
_DEFAULT_EXPIRY = "30"


def _rotate(old: str, host: str, expiry_days: int) -> str:
    now = datetime.datetime.now(datetime.UTC)
    expires_at = (now + datetime.timedelta(days=expiry_days)).date().isoformat()
    resp = httpx2.post(
        f"{host}/api/v4/personal_access_tokens/self/rotate",
        headers={"PRIVATE-TOKEN": old},
        data={"expires_at": expires_at},
        timeout=30.0,
    )
    resp.raise_for_status()
    return resp.json()["token"]


def _rotate_cfg(old: str, cfg: dict[str, str]) -> str:
    return _rotate(old, cfg["host"], int(cfg["expiry"]))


ROTATOR = base.Rotator(
    name="gitlab",
    rotate=_rotate_cfg,
    knobs=(
        base.Knob("host", _DEFAULT_HOST, "GitLab instance base URL"),
        base.Knob("expiry", _DEFAULT_EXPIRY, "new token lifetime in days"),
    ),
    help="GitLab personal access token (self-rotation)",
)

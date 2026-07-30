"""Rotator: GitLab personal access token (self-rotation).

Env: GITLAB_PAT_SECRET_ID (required), GITLAB_HOST (default https://gitlab.com),
     EXPIRY_DAYS (default 30). The PAT needs `api` scope (or `self_rotate` on
     GitLab >= 17.7) or the self-rotate endpoint returns 403.
"""
import os
from datetime import datetime, timedelta, timezone

import httpx

from ..core import SecretStore, rotate_secret


def _rotate(old: str) -> str:
    host = os.environ.get("GITLAB_HOST", "https://gitlab.com")
    days = int(os.environ.get("EXPIRY_DAYS", "30"))
    expires_at = (datetime.now(timezone.utc) + timedelta(days=days)).date().isoformat()
    resp = httpx.post(
        f"{host}/api/v4/personal_access_tokens/self/rotate",
        headers={"PRIVATE-TOKEN": old},
        data={"expires_at": expires_at},
        timeout=30.0,
    )
    resp.raise_for_status()
    return resp.json()["token"]


def run(store: SecretStore) -> None:
    secret_id = os.environ["GITLAB_PAT_SECRET_ID"]
    rotate_secret(store, secret_id, _rotate)

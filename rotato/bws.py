"""Thin wrapper over the Bitwarden Secrets Manager SDK.

Isolated here so the rest of rotato depends only on get_value/set_value, and so
the SDK is imported lazily (tests use a fake store and never import it).
Verify the method signatures against your installed `bitwarden-sdk` version.
"""
import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class Secret:
    id: str
    key: str
    value: str
    note: str
    organization_id: str
    project_id: Optional[str]


class BwsClient:
    """Reads/writes a single secret's value in Bitwarden Secrets Manager."""

    def __init__(self, access_token: Optional[str] = None):
        from bitwarden_sdk import (
            BitwardenClient,
            DeviceType,
            client_settings_from_dict,
        )

        self._client = BitwardenClient(
            client_settings_from_dict(
                {
                    "apiUrl": os.environ.get("BWS_API_URL", "https://api.bitwarden.com"),
                    "identityUrl": os.environ.get(
                        "BWS_IDENTITY_URL", "https://identity.bitwarden.com"
                    ),
                    "deviceType": DeviceType.SDK,
                    "userAgent": "rotato",
                }
            )
        )
        token = access_token or os.environ["BWS_ACCESS_TOKEN"]
        self._client.auth().login_access_token(token)

    def get(self, secret_id: str) -> Secret:
        data = self._client.secrets().get(secret_id).data
        return Secret(
            id=data.id,
            key=data.key,
            value=data.value,
            note=data.note or "",
            organization_id=data.organization_id,
            project_id=data.project_id,
        )

    def get_value(self, secret_id: str) -> str:
        return self.get(secret_id).value

    def set_value(self, secret_id: str, value: str) -> None:
        # update() replaces the whole secret, so preserve everything but value.
        s = self.get(secret_id)
        self._client.secrets().update(
            id=s.id,
            key=s.key,
            value=value,
            note=s.note,
            organization_id=s.organization_id,
            project_ids=[s.project_id] if s.project_id else None,
        )

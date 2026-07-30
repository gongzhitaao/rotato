"""Rotation framework: read -> rotate -> write -> verify."""

from collections.abc import Callable
from typing import Protocol


class SecretStore(Protocol):
    def get_value(self, secret_id: str) -> str: ...
    def set_value(self, secret_id: str, value: str) -> None: ...


class RotationError(Exception):
    pass


def rotate_secret(
    store: SecretStore,
    secret_id: str,
    rotate_fn: Callable[[str], str],
) -> None:
    """Rotate one secret and verify the new value was stored.

    rotate_fn receives the current value and must return the new one, doing
    whatever provider-specific mint/revoke dance is required.
    """
    old = store.get_value(secret_id)
    if not old:
        raise RotationError(f"could not read current value for {secret_id}")

    new = rotate_fn(old)
    if not new:
        raise RotationError(
            f"rotate function produced no new value for {secret_id}"
        )

    store.set_value(secret_id, new)

    # Verify the store really has it — otherwise the new credential lives
    # nowhere. Surface the value (-> logs) as break-glass for manual recovery.
    if store.get_value(secret_id) != new:
        raise RotationError(
            f"write-back verify FAILED for {secret_id}; "
            f"recover this value then re-rotate NOW: {new}"
        )

    print(f"OK: rotated {secret_id}")

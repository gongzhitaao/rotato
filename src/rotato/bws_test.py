"""Tests for the Bitwarden Secrets Manager wrapper (no real SDK/network)."""

# Tests construct a client without __init__ and reach _to_secret / _client.
# pylint: disable=protected-access

import types

from rotato import bws


def _data(**kw):
    base = {
        "id": "u1",
        "key": "k",
        "value": "v",
        "note": "n",
        "organization_id": "org",
        "project_id": "p",
        "revision_date": "2026-01-01T00:00:00Z",
    }
    base.update(kw)
    return types.SimpleNamespace(**base)


def test_to_secret_coerces_fields():
    s = bws.BwsClient._to_secret(_data())
    assert (s.id, s.key, s.value, s.note) == ("u1", "k", "v", "n")
    assert s.project_id == "p"
    assert s.revision_date == "2026-01-01T00:00:00Z"


def test_to_secret_handles_missing_optionals():
    s = bws.BwsClient._to_secret(
        _data(note=None, project_id=None, revision_date=None)
    )
    assert s.note == ""
    assert s.project_id is None
    assert s.revision_date == ""


def test_list_secrets_maps_sync_response():
    client = object.__new__(bws.BwsClient)
    resp = types.SimpleNamespace(
        data=types.SimpleNamespace(secrets=[_data(id="a"), _data(id="b")])
    )
    secrets_api = types.SimpleNamespace(sync=lambda org, since: resp)
    client._client = types.SimpleNamespace(secrets=lambda: secrets_api)
    assert [s.id for s in client.list_secrets("org")] == ["a", "b"]

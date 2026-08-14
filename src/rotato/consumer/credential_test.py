"""Tests for producing the usable credential (rotato print)."""

# Tests stub the module's private raw-fetch primitive.
# pylint: disable=protected-access

import pytest

import rotato.consumer.config as config
import rotato.consumer.credential as credential


@pytest.fixture(autouse=True)
def _isolate(tmp_path, monkeypatch):
    monkeypatch.setenv("ROTATO_CONFIG_DIR", str(tmp_path))


def test_token_entry_returns_raw_value(monkeypatch):
    config.record_secret("gl", config.Entry(uuid="U", kind=config.KIND_TOKEN))
    monkeypatch.setattr(
        credential, "_raw_value", lambda u: "PATVALUE" if u == "U" else "?"
    )
    assert credential.usable_credential("gl") == "PATVALUE"


def test_github_app_entry_mints_token(monkeypatch):
    config.record_secret(
        "gh",
        config.Entry(
            uuid="P",
            kind=config.KIND_GITHUB_APP,
            app_id="1",
            installation_id="2",
        ),
    )
    monkeypatch.setattr(credential, "_raw_value", lambda u: "PEMDATA")
    seen = {}

    def fake_mint(
        pem, app_id, installation_id, api=credential.github.DEFAULT_API
    ):
        seen.update(
            pem=pem, app_id=app_id, installation_id=installation_id, api=api
        )
        return "ghs_minted"

    monkeypatch.setattr(credential.github, "mint_token", fake_mint)
    assert credential.usable_credential("gh") == "ghs_minted"
    assert seen["pem"] == "PEMDATA"
    assert seen["app_id"] == "1"
    assert seen["installation_id"] == "2"


def test_uninstalled_exits():
    with pytest.raises(SystemExit):
        credential.usable_credential("nope")


def test_rejects_control_char_value(monkeypatch):
    config.record_secret("gl", config.Entry(uuid="U", kind=config.KIND_TOKEN))
    monkeypatch.setattr(credential, "_raw_value", lambda u: "abc\nhost=evil")
    with pytest.raises(SystemExit):
        credential.usable_credential("gl")


def test_strips_trailing_newline(monkeypatch):
    config.record_secret("gl", config.Entry(uuid="U", kind=config.KIND_TOKEN))
    monkeypatch.setattr(credential, "_raw_value", lambda u: "PATVALUE\n")
    assert credential.usable_credential("gl") == "PATVALUE"


def test_rejects_leading_newline(monkeypatch):
    config.record_secret("gl", config.Entry(uuid="U", kind=config.KIND_TOKEN))
    monkeypatch.setattr(credential, "_raw_value", lambda u: "\nPATVALUE")
    with pytest.raises(SystemExit):
        credential.usable_credential("gl")


def test_raw_value_reads_token_and_fetches(monkeypatch):
    monkeypatch.setattr(credential.config, "read_token", lambda: "TOK")
    seen = {}

    class FakeClient:
        def __init__(self, access_token=None):
            seen["token"] = access_token

        def get_value(self, uuid):
            seen["uuid"] = uuid
            return "VALUE"

    monkeypatch.setattr(credential.bws, "BwsClient", FakeClient)
    assert credential._raw_value("U1") == "VALUE"
    assert seen == {"token": "TOK", "uuid": "U1"}

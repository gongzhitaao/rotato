"""Tests for tag-driven batch rotation."""

# pylint: disable=protected-access

import datetime
import types

from rotato import roster
from rotato.rotators import base

_NOW = datetime.datetime(2026, 8, 17, tzinfo=datetime.UTC)


def _raise():
    raise RuntimeError("provider 500")


def _sec(sid, key, note, age_days=0.0):
    revision = (_NOW - datetime.timedelta(days=age_days)).isoformat()
    return types.SimpleNamespace(
        id=sid, key=key, note=note, revision_date=revision
    )


class _FakeStore:
    def __init__(self, values):
        self._v = dict(values)

    def get_value(self, sid):
        return self._v.get(sid, "")

    def set_value(self, sid, value):
        self._v[sid] = value


def _reg(monkeypatch, rotate=lambda old, cfg: old + "-new"):
    rotator = base.Rotator(
        name="gitlab",
        rotate=rotate,
        knobs=(base.Knob("host", "https://gitlab.com", "url"),),
        help="gitlab",
    )
    monkeypatch.setattr(roster.rotators, "REGISTRY", {"gitlab": rotator})
    return rotator


def test_rotates_tagged_secret(monkeypatch):
    _reg(monkeypatch)
    store = _FakeStore({"s1": "OLD"})
    report = roster.rotate_tagged(
        store, [_sec("s1", "prod", "#rotato=gitlab")], _NOW
    )
    assert store._v["s1"] == "OLD-new"
    assert [i.key for i in report.rotated] == ["prod"]
    assert roster.render(report) == 0


def test_untagged_secret_skipped(monkeypatch):
    _reg(monkeypatch)
    store = _FakeStore({"s1": "OLD"})
    report = roster.rotate_tagged(
        store, [_sec("s1", "misc", "no tags here")], _NOW
    )
    assert store._v["s1"] == "OLD"  # untouched
    assert not report.rotated and not report.failed and not report.stale


def test_unknown_type_is_failure(monkeypatch):
    _reg(monkeypatch)
    store = _FakeStore({"s1": "OLD"})
    report = roster.rotate_tagged(
        store, [_sec("s1", "x", "#rotato=nope")], _NOW
    )
    assert [i.status for i in report.failed] == ["unknown-type"]
    assert roster.render(report) == 1


def test_one_failure_does_not_abort_batch(monkeypatch):
    _reg(
        monkeypatch,
        lambda old, cfg: _raise() if old == "BAD" else old + "-new",
    )
    store = _FakeStore({"a": "OK", "b": "BAD"})
    report = roster.rotate_tagged(
        store,
        [_sec("a", "a", "#rotato=gitlab"), _sec("b", "b", "#rotato=gitlab")],
        _NOW,
    )
    assert store._v["a"] == "OK-new"  # good one still rotated
    assert [i.key for i in report.rotated] == ["a"]
    assert [i.key for i in report.failed] == ["b"]
    assert roster.render(report) == 1


def test_staleness_flags_overdue_secret(monkeypatch):
    _reg(monkeypatch)
    store = _FakeStore({"old": "V", "fresh": "V"})
    secrets = [
        _sec("old", "old", "#rotato=gitlab", age_days=60),
        _sec("fresh", "fresh", "#rotato=gitlab", age_days=3),
    ]
    report = roster.rotate_tagged(store, secrets, _NOW)  # default 21d
    assert report.stale == ["old"]


def test_cadence_tag_tightens_staleness(monkeypatch):
    _reg(monkeypatch)
    store = _FakeStore({"s": "V"})
    secrets = [_sec("s", "s", "#rotato=gitlab #cadence=7", age_days=10)]
    report = roster.rotate_tagged(store, secrets, _NOW)  # 10d > 7d cadence
    assert report.stale == ["s"]


def test_config_passed_from_tags(monkeypatch):
    seen = {}
    _reg(monkeypatch, lambda old, cfg: seen.update(cfg) or "new")
    store = _FakeStore({"s": "OLD"})
    secret = _sec("s", "s", "#rotato=gitlab #host=https://gl.internal")
    roster.rotate_tagged(store, [secret], _NOW)
    assert seen["host"] == "https://gl.internal"


def test_naive_timestamp_does_not_crash_batch(monkeypatch):
    # A tz-naive revision_date must not raise out of the loop (assume UTC).
    _reg(monkeypatch)
    store = _FakeStore({"s": "OLD"})
    naive = types.SimpleNamespace(
        id="s",
        key="s",
        note="#rotato=gitlab",
        revision_date="2026-01-01T00:00:00",
    )
    report = roster.rotate_tagged(store, [naive], _NOW)
    assert [i.key for i in report.rotated] == ["s"]
    assert report.stale == ["s"]  # ~7 months old > 21d default


def test_age_days_handles_bad_and_empty_dates():
    assert roster._age_days("", _NOW) is None
    assert roster._age_days("not-a-date", _NOW) is None


def test_render_emits_alert_prefixes(capsys):
    # These exact strings are matched by deploy/add-alert.sh log-based policies.
    report = roster.Report(
        rotated=[roster.Item("i", "prod", "gitlab", "rotated")],
        failed=[roster.Item("j", "bad", "gitlab", "failed", "boom")],
        stale=["overdue"],
    )
    assert roster.render(report) == 1
    out = capsys.readouterr().out
    assert "rotato-alert STALE overdue" in out
    assert "rotato-alert FAILED bad (gitlab): boom" in out
    assert "roster: rotated 1" in out


def test_render_stale_without_failure_exits_zero(capsys):
    report = roster.Report(stale=["overdue"])
    assert roster.render(report) == 0
    assert "rotato-alert STALE overdue" in capsys.readouterr().out

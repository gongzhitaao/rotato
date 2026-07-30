import pytest

from rotato.core import RotationError, rotate_secret


class FakeStore:
    def __init__(self, initial, readonly=False):
        self._v = {"sid": initial}
        self._readonly = readonly

    def get_value(self, sid):
        return self._v.get(sid, "")

    def set_value(self, sid, value):
        if not self._readonly:   # readonly models a write that silently fails
            self._v[sid] = value


def test_happy_path(capsys):
    store = FakeStore("OLD")
    rotate_secret(store, "sid", lambda old: "NEW")
    assert store._v["sid"] == "NEW"
    assert "OK: rotated sid" in capsys.readouterr().out


def test_unreadable_current_value():
    store = FakeStore("")
    with pytest.raises(RotationError, match="could not read"):
        rotate_secret(store, "sid", lambda old: "NEW")


def test_rotate_fn_empty():
    store = FakeStore("OLD")
    with pytest.raises(RotationError, match="no new value"):
        rotate_secret(store, "sid", lambda old: "")


def test_rotate_fn_raises_propagates():
    store = FakeStore("OLD")

    def boom(old):
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError):
        rotate_secret(store, "sid", boom)


def test_verify_failure_surfaces_value():
    # break-glass: the new value must appear in the error for manual recovery
    store = FakeStore("OLD", readonly=True)
    with pytest.raises(RotationError, match="NEW"):
        rotate_secret(store, "sid", lambda old: "NEW")

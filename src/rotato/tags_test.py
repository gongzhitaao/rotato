"""Tests for note-tag parsing."""

from rotato import tags


def test_parse_basic():
    note = "#rotato=gitlab #host=https://gitlab.com #expiry=30"
    assert tags.parse(note) == {
        "rotato": "gitlab",
        "host": "https://gitlab.com",
        "expiry": "30",
    }


def test_parse_amid_prose_and_newlines():
    note = "prod deploy token.\nrotate: #rotato=gitlab\nexpires soon #expiry=7"
    assert tags.parse(note) == {"rotato": "gitlab", "expiry": "7"}


def test_value_keeps_colons_and_slashes():
    assert tags.parse("#host=https://gl.example.com:8443/x")["host"] == (
        "https://gl.example.com:8443/x"
    )


def test_adjacent_tags_without_space_separate():
    assert tags.parse("#a=1#b=2") == {"a": "1", "b": "2"}


def test_trailing_sentence_punctuation_stripped():
    note = "rotate it: #rotato=gitlab. see #expiry=30, done."
    parsed = tags.parse(note)
    assert parsed["rotato"] == "gitlab"
    assert parsed["expiry"] == "30"


def test_parse_empty_and_none():
    assert not tags.parse("")
    assert not tags.parse(None)


def test_rotator_type():
    assert tags.rotator_type(tags.parse("#rotato=gitlab")) == "gitlab"
    assert tags.rotator_type(tags.parse("just a plain note")) is None

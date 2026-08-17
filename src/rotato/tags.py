"""Parse rotato tags out of a secret's free-text Bitwarden note.

Grammar: whitespace-delimited ``#key=value`` tokens anywhere in the note; a
value runs to the next whitespace or ``#`` (so adjacent tags without a space
still separate). ``#rotato=<type>`` is the enrollment tag — its value selects
the rotator; a note without it is not enrolled for rotation.

    #rotato=gitlab  #host=https://gitlab.example.com  #expiry=30

Kept deliberately dumb (one regex, no ordering, tolerates surrounding prose)
because notes are human-edited. Values cannot contain whitespace or ``#``, and
trailing sentence punctuation is stripped so ``rotate it: #rotato=gitlab.`` in
prose still yields ``gitlab``.
"""

import re

ENROLL = "rotato"

_TAG = re.compile(r"#(\w+)=([^\s#]+)")
_TRAILING_PUNCT = ".,;:!?"


def parse(note: str) -> dict[str, str]:
    """Extract every ``#key=value`` tag from a note into a dict."""
    return {
        key: value.rstrip(_TRAILING_PUNCT)
        for key, value in _TAG.findall(note or "")
    }


def rotator_type(parsed: dict[str, str]) -> str | None:
    """The enrolled rotator type, or None if there is no ``#rotato=`` tag."""
    return parsed.get(ENROLL)

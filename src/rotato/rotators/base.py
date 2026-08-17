"""Rotator type: the rotate function plus the config knobs it accepts.

A rotator is provider logic ("given the old value, produce the new one") plus a
declaration of the ``#key=value`` note tags it reads. Declaring the knobs here
keeps ``rotato list tags`` in sync with the code and gives each knob a default,
so a secret's note only needs the non-default overrides.
"""

import dataclasses
from collections.abc import Callable


@dataclasses.dataclass(frozen=True)
class Knob:
    """One ``#key=value`` config tag a rotator reads, with its default."""

    name: str
    default: str
    help: str


@dataclasses.dataclass(frozen=True)
class Rotator:
    """A rotator type: its rotate function plus the config knobs it reads."""

    name: str
    rotate: Callable[[str, dict[str, str]], str]
    knobs: tuple[Knob, ...]
    help: str

    def config(self, tags: dict[str, str]) -> dict[str, str]:
        """Resolve this rotator's config: knob defaults overlaid with tags."""
        cfg = {k.name: k.default for k in self.knobs}
        for k in self.knobs:
            if k.name in tags:
                cfg[k.name] = tags[k.name]
        return cfg

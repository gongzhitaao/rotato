"""Registry mapping rotator type -> Rotator (rotate fn + declared config knobs).

The rotator's ``name`` is the value of a secret's ``#rotato=<name>`` note tag.
"""

from . import gitlab
from .base import Knob, Rotator

REGISTRY: dict[str, Rotator] = {
    gitlab.ROTATOR.name: gitlab.ROTATOR,
}

__all__ = ["Knob", "Rotator", "REGISTRY"]

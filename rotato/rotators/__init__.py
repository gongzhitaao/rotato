"""Rotator registry. Add a module exposing run(store) and register it by name."""
from . import gitlab_pat

REGISTRY = {
    "gitlab-pat": gitlab_pat.run,
}

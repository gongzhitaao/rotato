"""Registry mapping rotator name -> run(store)."""

from . import gitlab_pat

REGISTRY = {
    "gitlab-pat": gitlab_pat.run,
}

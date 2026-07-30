# pylint: disable=invalid-name  # module is executed as `python -m rotato`
"""rotato entrypoint / dispatcher.

Usage: python -m rotato <rotator-name>   (or set ROTATOR in the environment)
Looks the name up in the registry and runs it against a Bitwarden client.
"""

import os
import sys

from .bws import BwsClient
from .rotators import REGISTRY


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    name = argv[0] if argv else os.environ.get("ROTATOR", "")
    if not name:
        print(
            "usage: python -m rotato <rotator-name>  (or set ROTATOR)",
            file=sys.stderr,
        )
        return 2

    run = REGISTRY.get(name)
    if run is None:
        print(f"unknown rotator: {name}", file=sys.stderr)
        return 2

    # Top-level guard: the message (incl. any break-glass value) goes to logs.
    try:
        run(BwsClient())
    except Exception as exc:  # pylint: disable=broad-exception-caught
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

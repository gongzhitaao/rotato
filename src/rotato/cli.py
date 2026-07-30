"""rotato CLI / dispatcher.

Runs a named rotator (see the registry) against a Bitwarden client. Invoked as
the `rotato` console script: `rotato <name>`; the name may also come from the
ROTATOR environment variable.
"""

import os
import sys

from .bws import BwsClient
from .rotators import REGISTRY


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    name = argv[0] if argv else os.environ.get("ROTATOR", "")
    if not name:
        print("usage: rotato <rotator-name>  (or set ROTATOR)", file=sys.stderr)
        return 2

    run = REGISTRY.get(name)
    if run is None:
        print(f"unknown rotator: {name}", file=sys.stderr)
        return 2

    # Let failures propagate: the traceback (incl. any RotationError break-glass
    # value) goes to stderr -> Cloud Logging, and the non-zero exit trips the
    # failure alert.
    run(BwsClient())
    return 0

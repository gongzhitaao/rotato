"""Consumer-side commands: register secrets and use them on a machine.

These back the `rotato install / print / setup / list` subcommands run on
laptops and VMs (as opposed to the server-side rotators). Everything reads this
machine's read-only BWS token and the installed-secret registry under
~/.config/rotato/; nothing here needs a repo checkout.
"""

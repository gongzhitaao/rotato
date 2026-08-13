"""Consumer-side commands: bootstrap a machine and fetch credentials.

These back the `rotato install / fetch / github-token / git-credential`
subcommands run on laptops and VMs (as opposed to the server-side rotators).
Everything reads this machine's read-only BWS token and the name -> uuid map
under ~/.config/rotato/; nothing here needs a repo checkout.
"""

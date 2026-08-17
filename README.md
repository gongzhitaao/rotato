# rotato

Serverless secret/key rotation into
[Bitwarden Secrets Manager](https://bitwarden.com/products/secrets-manager/).

A scheduled [Cloud Run job](https://cloud.google.com/run/docs/create-jobs)
rotates an expiring credential (e.g. a GitLab PAT) and writes the fresh value
back to Bitwarden. Every machine then fetches the *current* value on demand, so
the secret is never written to disk and rotations are transparent.

## Install

```bash
uv tool install rotato      # or: pipx install rotato
```

## Consumer usage (laptop / VM)

Register a secret on the machine, then use it — no repo checkout required.

```bash
# a plain token (e.g. a GitLab PAT)
rotato install <secret-uuid> --name gitlab-pat

# a GitHub App private key (a short-lived installation token is minted on use)
rotato install <pem-uuid> --name gh --github --app-id <id> --installation-id <id>
```

`install` records the secret (and, on first run, prompts for this machine's
read-only Bitwarden token). Then:

```bash
rotato print <name|uuid>            # print the usable credential to stdout
rotato list  secrets               # what's installed here
rotato list  rotators              # rotator types this build supports
rotato list  tags                  # the note tags that enroll a secret
```

Wire git to an installed secret (writes a credential helper that calls
`rotato print`, so rotations are picked up automatically):

```bash
rotato setup gitlab <name> --user <git-user>    # gitlab.com
rotato setup github <name>                      # github.com (App installation token)
rotato setup git    <name> --user <u> --host <h>  # any git host
git -C <a-repo> ls-remote                        # git now authenticates via Bitwarden
```

## Shell completion

`rotato` supports tab-completion via
[argcomplete](https://pypi.org/project/argcomplete/) — including **installed
secret names** for `print`/`setup` (names only; never secret values).

The `register-python-argcomplete` generator ships with argcomplete, not rotato,
so `uv tool install rotato` doesn't put it on PATH — install argcomplete as a
tool too (once), then register `rotato` in your shell rc:

```bash
uv tool install argcomplete

# bash — ~/.bashrc
eval "$(register-python-argcomplete rotato)"

# zsh — ~/.zshrc (with compinit loaded)
eval "$(register-python-argcomplete -s zsh rotato)"

# fish
register-python-argcomplete -s fish rotato > ~/.config/fish/completions/rotato.fish
```

Then `rotato <tab>` lists subcommands, `rotato print <tab>` lists installed
secrets, `rotato setup <tab>` lists `github gitlab git`, and so on.

## Server side

`rotato refresh` (the Cloud Run job entrypoint) rotates **every secret tagged
for rotation** in the Bitwarden org: read current → rotate at the provider →
write back → verify. A secret is enrolled by a `#rotato=<type>` tag in its
Bitwarden note (`rotato list tags` shows the grammar), so adding one needs no
redeploy.

## Documentation

Full design, invariants, deployment, and the enroll / "add a rotator" guides:
[README.org](https://github.com/gongzhitaao/rotato/blob/main/README.org).

## License

[MIT](https://github.com/gongzhitaao/rotato/blob/main/LICENSE).

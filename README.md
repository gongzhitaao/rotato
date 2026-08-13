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
rotato list  rotators              # rotators this build supports
```

Wire git to an installed secret (writes a credential helper that calls
`rotato print`, so rotations are picked up automatically):

```bash
rotato setup gitlab <name> --user <git-user>    # gitlab.com
rotato setup github <name>                      # github.com (App installation token)
rotato setup git    <name> --user <u> --host <h>  # any git host
git -C <a-repo> ls-remote                        # git now authenticates via Bitwarden
```

## Server side

`rotato refresh <rotator-name>` runs a rotator (the Cloud Run job entrypoint):
read current → rotate at the provider → write back to Bitwarden → verify.
`ROTATOR` env selects the rotator.

## Documentation

Full design, invariants, deployment, and "add a rotator" guide:
[README.org](https://github.com/gongzhitaao/rotato/blob/main/README.org).

## License

[MIT](https://github.com/gongzhitaao/rotato/blob/main/LICENSE).

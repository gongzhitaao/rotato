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

Bootstrap a machine once — no repo checkout required:

```bash
# GitLab PAT (or any Bitwarden token) as a git credential
rotato install <secret-uuid> --user <git-user>

# GitHub App mode: mint a short-lived installation token per git op
rotato install <pem-uuid> --github --app-id <id> --installation-id <id>
```

`install` writes this machine's read-only Bitwarden token to
`~/.config/rotato/`, records a friendly `name -> uuid` map, and points git's
credential helper at `rotato`. After that:

```bash
rotato fetch <name|uuid>          # print a secret's current value, read-only
rotato github-token <name|uuid> --app-id <id> --installation-id <id>
git -C <a-repo> ls-remote         # git now authenticates via Bitwarden
```

## Server side

The rotation job runs as `rotato run <rotator-name>` (also the container
entrypoint); `ROTATOR` selects the rotator. Deploying the Cloud Run job,
scheduler, and alerting is covered in the full documentation.

## Documentation

Full design, invariants, deployment, and "add a rotator" guide:
[README.org](https://github.com/gongzhitaao/rotato/blob/main/README.org).

## License

[MIT](https://github.com/gongzhitaao/rotato/blob/main/LICENSE).

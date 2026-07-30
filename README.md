# rotato

Serverless secret/key rotation. A scheduled [Cloud Run job](https://cloud.google.com/run/docs/create-jobs)
rotates expiring credentials and writes the fresh value back to
[Bitwarden Secrets Manager](https://bitwarden.com/products/secrets-manager/),
so your laptop and any VM always fetch a current secret and nothing needs a
long-running server.

```
Cloud Scheduler (cron)  ──►  Cloud Run job  ──►  rotate at provider
                                     │              │
                                     └──────────────┴──►  write back to Bitwarden
                                                          (verified)

  laptop / VM  ──►  git credential helper  ──►  bws secret get  (read-only)
```

## Design rules

- **One rotator per secret.** Rotation revokes the old value immediately; only
  this job may rotate. Every consumer (laptop, VM) is **read-only**.
- **Verify write-back.** A rotation that succeeds but fails to store the new
  value leaves the credential nowhere. The framework re-reads Bitwarden and
  fails loudly (printing the value to logs as break-glass) if it doesn't match.
- **No retries.** Jobs run with `--max-retries=0`; a half-done rotation can't be
  retried (the old token is already dead). The safety net is a **wide expiry
  margin** — rotate far more often than the token's lifetime (e.g. every 14 days
  on a 30-day token) so one failed run has room to recover — plus alerting.

## Layout

```
rotato.sh                     dispatcher: runs rotators/<name>.sh
lib/common.sh                 rotato_run: bws read -> rotate -> write -> verify
rotators/<name>.sh            per-secret logic; defines rotato_main
Dockerfile                    debian + bws + jq + curl
deploy/rotato.env(.example)   the one fill-in-and-run config (gitignored: rotato.env)
deploy/setup.sh               one-time shared infra (APIs, registry, image, SAs)
deploy/add-rotator.sh         one Cloud Run job + scheduler per secret
deploy/add-alert.sh           email alert on a rotator's failed executions
deploy/run.sh                 setup + add-rotator + add-alert, end to end
test/                         bats unit tests (test/run.sh installs bats if needed)
```

All `deploy/*` scripts are **idempotent** — re-run any of them to change the
schedule, rebuild the image, or replace the bootstrap token without creating
duplicates.

## Prerequisites

In Bitwarden Secrets Manager:
1. A **secret** holding the current credential — note its UUID.
2. A **`rotator` machine account** with **read+write** on that secret's project
   → its access token is the bootstrap secret (`BWS_ACCESS_TOKEN`).
3. Separate **read-only** machine accounts for each consumer (laptop, VM).

For the GitLab PAT specifically, the token needs **`api`** scope (or
`self_rotate` on GitLab ≥ 17.7) or self-rotation returns 403.

## Deploy

One env file holds everything. The only secret in it is `BWS_ACCESS_TOKEN`, and
it is needed **only to bootstrap** — `setup.sh` uploads it to Secret Manager,
after which the job reads it from there and you can blank it locally.

```bash
cp deploy/rotato.env.example deploy/rotato.env   # fill in project, token, secret UUID
deploy/run.sh                                    # setup + deploy the rotator
gcloud run jobs execute rotato-gitlab-pat --region <REGION> --wait   # smoke test
```

`run.sh` chains `setup.sh`, `add-rotator.sh`, and `add-alert.sh`; run them
separately if you prefer. All accept an optional env-file path (default
`deploy/rotato.env`).

Set `ALERT_EMAIL` in the env file to be emailed when a rotation job fails —
without it a failed run is silent until the token expires. Leave it blank to
skip alerting.

## Add another secret

1. Write `rotators/<name>.sh` defining `rotato_main`, which calls
   `rotato_run <secret_id> <rotate_fn>`. `rotate_fn` receives the old value on
   `$1` and prints the new value to stdout (doing whatever provider-specific
   mint/revoke dance is required).
2. `deploy/setup.sh` once more to rebuild the image with the new script.
3. Copy `deploy/rotato.env` to `deploy/<name>.env`, edit the rotator section,
   then `deploy/add-rotator.sh deploy/<name>.env`.

## Tests

```bash
test/run.sh    # installs bats via 'npm install -g bats' if missing; needs jq
```

Stubs for `bws`/`curl` (`test/bin/`) exercise the framework, the gitlab-pat
rotator, and the write-back verify / break-glass path without touching any real
service.

## Consuming the secret (laptop / VM)

Install `bws`, place a **read-only** machine-account token, and point git at a
credential helper that fetches on demand:

```gitconfig
[credential "https://gitlab.com"]
    username = <user>
    helper = "!f() { test \"$1\" = get && \
      echo \"password=$(BWS_ACCESS_TOKEN=$(cat ~/.config/bws/token) \
      bws secret get $GITLAB_PAT_SECRET_ID | jq -r .value)\"; }; f"
```

The PAT is never written to disk and automatically tracks rotations.

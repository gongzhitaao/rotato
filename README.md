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
deploy/config.env(.example)   GCP project/region (gitignored: config.env)
deploy/setup.sh               one-time shared infra (APIs, registry, image, SAs)
deploy/add-rotator.sh         one Cloud Run job + scheduler per secret
deploy/rotators/<name>.env    per-secret deploy config (gitignored)
```

## Prerequisites (per secret)

In Bitwarden Secrets Manager:
1. A **secret** holding the current credential — note its UUID.
2. A **`rotator` machine account** with **read+write** on that secret's project.
3. Separate **read-only** machine accounts for each consumer (laptop, VM).

For the GitLab PAT specifically, the token needs **`api`** scope (or
`self_rotate` on GitLab ≥ 17.7) or self-rotation returns 403.

## One-time setup

```bash
cp deploy/config.env.example deploy/config.env    # edit project/region
deploy/setup.sh                                    # prompts for the rotator BWS token
```

## Add a rotator

```bash
cp deploy/rotators/gitlab-pat.env.example deploy/rotators/gitlab-pat.env
# edit: GITLAB_PAT_SECRET_ID, SCHEDULE, TIME_ZONE
deploy/add-rotator.sh deploy/rotators/gitlab-pat.env
gcloud run jobs execute rotato-gitlab-pat --region <REGION> --wait   # smoke test
```

## Add a new *kind* of secret

Write `rotators/<name>.sh` defining `rotato_main`, which calls
`rotato_run <secret_id> <rotate_fn>`. `rotate_fn` receives the old value on
`$1` and must print the new value to stdout (doing whatever provider-specific
mint/revoke dance is required). Then create `deploy/rotators/<name>.env` and run
`deploy/add-rotator.sh`. Rebuild the shared image with `deploy/setup.sh` so the
new script ships in the container.

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

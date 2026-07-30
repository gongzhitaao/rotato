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
src/rotato/cli.py             dispatcher: the `rotato` console script
src/rotato/core.py            rotate_secret: read -> rotate -> write -> verify
src/rotato/bws.py             Bitwarden Secrets Manager client (get/set value)
src/rotato/rotators/<name>.py per-secret logic; exposes run(store)
src/rotato/rotators/__init__.py  name -> rotator registry
src/rotato/**/*_test.py       colocated pytest tests (foo.py -> foo_test.py)
Dockerfile                    python:3.12-slim + the rotato package
deploy/rotato.env(.example)   the one fill-in-and-run config (gitignored: rotato.env)
deploy/setup.sh               one-time shared infra (APIs, registry, image, SAs)
deploy/add-rotator.sh         one Cloud Run job + scheduler per secret
deploy/add-alert.sh           email alert on a rotator's failed executions
deploy/run.sh                 setup + add-rotator + add-alert, end to end
consumer/rotato-fetch         read a secret value, read-only (bash)
consumer/rotato-git-credential  git credential helper over rotato-fetch
consumer/install.sh           one-time per-machine consumer setup
```

The rotation core is Python (real error handling, the Bitwarden SDK, mockable
tests); the `deploy/*` scripts stay bash since they only orchestrate `gcloud`.

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

1. Write `src/rotato/rotators/<name>.py` exposing `run(store)`, which calls
   `rotate_secret(store, secret_id, rotate_fn)`. `rotate_fn` receives the old
   value and returns the new one (doing whatever provider-specific mint/revoke
   dance is required). Register it in `src/rotato/rotators/__init__.py`.
2. `deploy/setup.sh` once more to rebuild the image with the new module.
3. Copy `deploy/rotato.env` to `deploy/<name>.env`, edit the rotator section,
   then `deploy/add-rotator.sh deploy/<name>.env`.

## Development & tests

Dependencies are managed with [uv](https://docs.astral.sh/uv/) — runtime deps in
`[project.dependencies]`; `pytest`, `ruff`, and `pylint` in the `dev` group; all
pinned in `uv.lock`.

```bash
uv sync                     # create .venv from the lockfile
uv run pytest               # tests (colocated *_test.py, found via config)
uv run ruff format          # format (80 cols, to match pylint)
uv run ruff check           # lint + import sort
uv run pylint src/rotato --ignore-patterns='.*_test\.py'   # Google config
```

Ruff and pytest config live in `pyproject.toml`; `.pylintrc` is Google's
[published config](https://google.github.io/styleguide/pylintrc), used verbatim.
Each module has a colocated `<name>_test.py` (Google style); pytest finds them
via `python_files`, they're excluded from pylint, and stripped from the Docker
image. Tests mock the Bitwarden client and the GitLab HTTP call, so they cover
the framework, the gitlab-pat rotator, and the write-back verify / break-glass
path without touching any real service.

## Consuming the secret (laptop / VM)

Each consumer machine fetches the **current** value from Bitwarden on demand, so
the PAT is never written to disk and rotations are transparent. Run once per
machine (needs `bws` + `jq`):

```bash
consumer/install.sh <secret-uuid> --user <git-user>   # add --dry-run to preview
```

It stores this machine's **read-only** BWS token at `~/.config/rotato/token`
(chmod 600), installs `rotato-fetch` + `rotato-git-credential` into
`~/.local/bin`, and points git at the helper for the host (default
`gitlab.com`; override with `--host`).

- **Another git host** (a second GitLab, a GitHub PAT): reuse the same helper —
  rerun `install.sh <other-uuid> --host <host> --user <user>`.
- **A non-git credential**: call the primitive directly, e.g.
  `export SOME_KEY="$(rotato-fetch <uuid>)"`.

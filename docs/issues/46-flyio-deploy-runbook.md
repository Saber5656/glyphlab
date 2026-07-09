# Title

Fly.io deploy configuration & operations runbook

# Summary

Provide the deploy-ready Fly.io configuration (`deploy/fly.toml`) and `deploy/RUNBOOK.md`
documenting exact bring-up, operations, and incident steps — with human-only actions
(account, payment, secrets, domain) explicitly marked. This closes the "deploy-ready" v1
definition (ADR-002 point 5).

# Context

v1 ends at *deployable*: an operator following the runbook, with no repo knowledge, must
reach a healthy public instance. Secrets are never set by agents (repo policy).

# Scope

`deploy/fly.toml`, `deploy/RUNBOOK.md`, `deploy/check_runbook.sh` (drift/format linter),
and a `ci.yml` step running `fly config validate` (SHA-pinned `superfly/flyctl-actions`
or a pinned flyctl install; no auth needed for validate) + the check script. No actual
deployment.

# Detailed Requirements

1. `fly.toml`:
   - `app = "glyphlab"` (placeholder; runbook notes rename), primary_region placeholder
     `nrt`.
   - `[build] dockerfile = "Dockerfile"` — paths in fly.toml resolve relative to the
     config file, and `fly deploy --config deploy/fly.toml` uses the config's directory
     as build context root by default; the runbook therefore always shows the exact form
     `fly deploy --config deploy/fly.toml --dockerfile deploy/Dockerfile .` executed from
     the repo root (build context = repo root, matching issue 45).
   - `[mounts]` volume `glyphlab_data` at `/data`.
   - `[http_service]`: internal_port 8080, force_https, `min_machines_running = 1`,
     `auto_stop_machines = false` (ADR-005), concurrency limits (soft 40 / hard 60
     connections), health check on `/healthz` (10 s interval, 5 s grace).
   - `[[vm]]` shared-cpu-1x, **1024 MB** (§21 ceiling: ≤ 800 MiB total RSS with one job
     child; runbook covers resize).
   - `[env]`: `GLYPHLAB_ENVIRONMENT=prod`, `GLYPHLAB_OBJECT_STORE=local`,
     `GLYPHLAB_RETENTION_DAYS=14`.
2. `RUNBOOK.md` sections (each step exact commands; human-only steps tagged **[HUMAN]**):
   - Prerequisites: flyctl install, **[HUMAN]** account + payment.
   - First deploy: `fly launch --no-deploy --copy-config`, **[HUMAN]** app rename/region,
     `fly volumes create glyphlab_data --size 3 --region <r>`, **[HUMAN]**
     `fly secrets set` (none required for local-store default — state that explicitly;
     Postgres/S3 variants listed with their secret names `GLYPHLAB_DATABASE_URL`,
     `GLYPHLAB_S3_SECRET_ACCESS_KEY`), `fly deploy`, smoke checks (healthz, create
     project, template download via curl).
   - Custom domain + TLS: `fly certs add` (**[HUMAN]** DNS).
   - Upgrades: `fly deploy` from a tagged release; migration note (entrypoint runs
     alembic; single machine ⇒ no concurrent-migration hazard).
   - Storage growth path: switch to Tigris — exact steps: `fly storage create` (prints
     credentials), then `fly secrets set GLYPHLAB_S3_SECRET_ACCESS_KEY=...` **[HUMAN]**
     and set in `[env]`: `GLYPHLAB_OBJECT_STORE=s3`, `GLYPHLAB_S3_ENDPOINT_URL`,
     `GLYPHLAB_S3_BUCKET`, `GLYPHLAB_S3_REGION`, `GLYPHLAB_S3_ACCESS_KEY_ID` (issue 26 /
     DESIGN §20 names), `fly deploy`. Data migration: none in v1 — deploy the S3 config
     fresh and let old volume-stored projects expire naturally (documented as the
     supported path).
   - Backup/restore: `fly volumes snapshots list/create`; SQLite-on-WAL snapshot caveat
     (KU-8) — snapshot while healthy, restore procedure.
   - Incident: logs (`fly logs`), ssh console, disk-full playbook (watermark 507s → grow
     volume), token-leak report handling (rotate = user deletes project; no admin token
     access — state the design honestly), abuse-spike playbook naming the exact knobs
     (issue 26 fields as env vars): `GLYPHLAB_RL_CREATE_PER_DAY`,
     `GLYPHLAB_RL_UPLOADS_PER_HOUR_IP`, `GLYPHLAB_MAX_UPLOADS_PER_PROJECT`,
     `GLYPHLAB_MAX_STORE_BYTES` → `fly deploy` (env change = redeploy).
   - Cost estimate table at small scale (~$5–7/月: 1 shared VM + 3 GB volume).
3. `deploy/check_runbook.sh` (runs in CI + Validation) asserts mechanically: every
   `GLYPHLAB_*` name in fly.toml/RUNBOOK.md exists in `settings.py`; RUNBOOK.md contains
   the required section headings (First deploy / Custom domain / Upgrades / Storage
   growth / Backup & restore / Incident playbooks / Cost); ≥ 6 `**[HUMAN]**` markers;
   exactly 4 incident playbooks; zero strings matching `glp_[A-Za-z0-9_\-]{20,}` or
   `AKIA[0-9A-Z]{16}` (secret-leak canaries).

# Acceptance Criteria

- [ ] `flyctl config validate --config deploy/fly.toml` passes locally and in CI.
- [ ] `bash deploy/check_runbook.sh` exits 0 (this single command proves: env-name drift,
      required sections, [HUMAN] markers, playbook count, secret canaries).

# Validation

```bash
flyctl config validate --config deploy/fly.toml
bash deploy/check_runbook.sh
```

# Dependencies

45.

# Non-goals

Actual deployment/operation (post-v1 human task), Cloud Run manifests (compatibility kept
via 12-factor design; docs note it as unsupported-but-possible), IaC beyond fly.toml.

# Design References

DESIGN §20 (Fly.io, canonical env names incl. ENVIRONMENT), §17.6 (rate knobs), §21 (vm
sizing), ADR-002 (deploy-ready boundary), ADR-005, research/03.

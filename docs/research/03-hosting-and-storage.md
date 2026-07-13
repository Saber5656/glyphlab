# Research: Hosting & Storage for the Public Service

- Date: 2026-07-08
- Status: informs DESIGN.md §14, §20 and ADR-005

## Question

Given the decisions "public hosted service, anonymous token projects, container PaaS,
personal/small-community scale, v1 = deploy-ready (not deployed)", which PaaS and storage
combination should the deploy artifacts target?

## Findings

### Fly.io (+ Tigris object storage) — primary target

- `fly storage create` provisions a **Tigris** S3-compatible bucket billed through the Fly
  account; no separate vendor account. Standard S3 API → works with `boto3`.
- Pricing (2026-07): first 5 GB standard storage free; ~$0.02/GB-month beyond; **no egress
  fees**; request pricing negligible at our scale (hundreds of uploads/month).
- Fly Machines support persistent volumes; scale-to-zero is possible but pauses background work
  — relevant to our in-process job worker (see risk below).

### Google Cloud Run — secondary compatibility target

- No persistent local disk; SQLite on local disk is not durable there → Postgres (Cloud SQL) +
  GCS/S3 storage would be required. More moving parts and cost than Fly for this scale.
- Conclusion: keep the app 12-factor (storage + DB behind interfaces, config via env) so Cloud
  Run remains *possible*, but ship first-class deploy config only for Fly.io.

### Architecture consequences

| Concern | Decision candidate |
|---|---|
| DB | SQLAlchemy against **SQLite (WAL) on a Fly volume** for v1 default; `DATABASE_URL` switch to Postgres supported and CI-tested, for growth/self-host |
| Object storage | `ObjectStore` interface: `LocalDiskStore` (default; volume-backed) and `S3Store` (Tigris/any S3). Hosted default = LocalDiskStore on the same volume for v1 simplicity; S3Store is the growth path and is what makes Cloud Run viable |
| Instances | **Pin to exactly 1 machine in v1** (SQLite + in-process worker are single-writer). Document as an explicit scale limit; multi-instance requires Postgres + external queue (v2) |
| Scale-to-zero | Disable auto-stop in v1 (jobs would be killed mid-run and cold starts break polling UX), or set `min_machines_running = 1`. A small always-on machine is ~$5/月 scale — acceptable |
| TLS/ingress | Terminated by Fly proxy; app trusts `Fly-Client-IP`/`X-Forwarded-For` from the platform only |

### Job-loss risk

In-process worker + PaaS restarts ⇒ a `running` job can die without transitioning. Mitigation:
job rows carry `lease_expires_at`; on startup and on each sweep, `running` jobs with expired
leases are reset to `queued` (bounded retries) or `failed`. This must be an explicit requirement
of the job-worker issue.

## Sources

- https://fly.io/docs/tigris/ — Tigris on Fly
- https://www.tigrisdata.com/pricing/ — storage pricing, free tier, zero egress
- https://fly.io/docs/database-storage-guides/ — volumes & storage guidance

# ADR-005: Single-machine service; SQLite + local volume default; DB/storage behind interfaces

- Status: Accepted (2026-07-08)
- Deciders: user (PaaS choice, scale assumption), Fable (design), per research/03

## Context

Deployment target is a container PaaS (Fly.io primary) at personal/small-community scale.
The service needs a DB (projects/jobs/glyphs) and blob storage (uploads/artifacts), and an
execution model for CPU-bound jobs.

## Decision

1. **Exactly one service instance** in v1 (`min_machines_running = 1`, auto-stop disabled).
2. Default persistence: **SQLite (WAL) + local object store**, both on one mounted volume
   (`/data`). Production-ready alternatives selectable purely by env: `DATABASE_URL` →
   Postgres (CI-tested), `OBJECT_STORE=s3` → any S3-compatible store (Tigris on Fly).
3. Jobs run against a DB-table queue with lease-expiry recovery (DESIGN §14.3); each
   claimed job executes in a **spawned child process** (default concurrency 1) so the hard
   timeout is enforced by process termination; no Redis/external queue in v1.
4. The core boundary interfaces are `ObjectStore` and SQLAlchemy models; nothing above them may
   assume filesystem locality.

## Rationale

- At target scale, one small always-on machine (~$5/mo) removes whole classes of work:
  distributed locking, queue infra, cache coherence.
- SQLite-on-volume is durable on Fly volumes and trivially self-hostable (docker-compose with a
  bind mount) — persona P3 gets one-command bring-up.
- Keeping Postgres and S3 code paths alive (and tested) prevents lock-in to the shortcut and
  keeps Cloud Run viable (no local disk there).

## Consequences

- Horizontal scaling is explicitly out (NG8); the documented growth path is D7 (Postgres +
  external queue + multi-machine), enabled by the interfaces above.
- A PaaS restart can kill a running job → mandatory lease-expiry requeue (bounded retries,
  `E_JOB_LOST`) — encoded in the job-worker issue.
- Scale-to-zero is forgone; documented in the runbook as a cost/behavior trade-off.

## Alternatives rejected

- **Postgres-only from day 1**: heavier self-host story and Fly cost for zero v1 benefit.
- **Serverless jobs (Cloud Run jobs, queues)**: vendor-specific, breaks the self-host parity
  requirement.
- **Redis-backed queue**: another stateful service to operate; DB-table queue suffices at
  this concurrency.

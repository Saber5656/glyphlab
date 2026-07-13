# Title

DB models & Alembic migrations (SQLite + Postgres)

# Summary

Implement the DESIGN §14.2 schema as SQLAlchemy 2.x models with Alembic migrations, working
identically on SQLite (WAL) and Postgres, plus the session/engine factory honoring
`GLYPHLAB_DATABASE_URL`.

# Context

Seven tables (§14.2: projects, uploads, glyphs, jobs, artifacts, tombstones,
abuse_events) carry the whole service state. Cascade and constraint behavior must be identical across both engines
because self-host defaults to SQLite while growth path is Postgres (ADR-005).

# Scope

`packages/service/src/glyphlab_service/db/{engine.py,models.py}` +
`packages/service/src/glyphlab_service/db/migrations/` (Alembic script location; ini at
`packages/service/alembic.ini` pointing there) + the `glyphlab-service-migrate` console
script (`[project.scripts]` in service pyproject → runs `alembic upgrade head` with
settings-derived URL; issue 45's entrypoint depends on it) + a `services-db` CI job +
tests. Adds service deps: `sqlalchemy`, `alembic` (+ `psycopg[binary]` as extra
`glyphlab-service[postgres]`). The `services-db` CI job must sync/install the
`glyphlab-service[postgres]` extra before setting `TEST_POSTGRES_URL=postgresql+psycopg://...`;
the Postgres half of the suite must not depend on a driver already present from the developer
environment.

# Detailed Requirements

1. `engine.py`: `make_engine(settings)` — sqlite URL gets `PRAGMA journal_mode=WAL`,
   `foreign_keys=ON` (event listener), `timeout=30`; Postgres gets pool_pre_ping. Sync
   engine + `Session` factory (no async in v1 — worker threads share the same factory).
2. `models.py`: all seven §14.2 tables (`projects`, `uploads`, `glyphs`, `jobs`,
   `artifacts`, `tombstones`, `abuse_events` — the latter two have NO project FK) with: UUIDs stored as 36-char strings (cross-engine), UTC
   datetimes (`TIMESTAMP` naive-UTC convention documented), JSON via `sqlalchemy.JSON`,
   CHECK constraints for all enum-ish columns, FKs `ondelete="CASCADE"`, indexes: `projects.token_hash` unique,
   `projects.expires_at`, `jobs(status, created_at)`, `uploads.project_id`,
   `artifacts(project_id, kind)`, `artifacts.job_id` (nullable, no FK constraint — jobs
   may be pruned independently), `glyphs` PK `(project_id, codepoint)`.
   Security-critical column spelled out (§14.2/§17.3 T2): `projects.token_hash =
   LargeBinary(32) NOT NULL UNIQUE` — the SHA-256 digest of the bearer token; the clear
   token never appears in any column.
3. Alembic: single initial revision; env.py reads the URL from Settings; migrations run
   ONLY via the `glyphlab-service-migrate` console script (never implicitly in app
   lifespan — predictable ops, documented in the runbook); tests invoke the alembic API
   programmatically.
4. Cross-engine CI: pytest fixtures run the full model test suite twice — sqlite tmpfile
   and Postgres when `TEST_POSTGRES_URL` is set. Extend `ci.yml` with a `services-db` job:
   `services: postgres: image: postgres:17 (digest-pinned), env POSTGRES_PASSWORD=test,
   options: --health-cmd="pg_isready" --health-interval=5s --health-timeout=5s
   --health-retries=10`, job env `TEST_POSTGRES_URL=postgresql+psycopg://postgres:test@
   localhost:5432/postgres`.
5. Tests: constraint violations (bad status string, duplicate token_hash, orphan upload)
   rejected on BOTH engines; cascade delete of a project removes uploads/glyphs/jobs/
   artifacts while tombstones persist; expires_at index used (EXPLAIN sanity on sqlite
   acceptable as smoke).

# Acceptance Criteria

- [ ] Migration cycle test (upgrade → downgrade base → upgrade, via alembic API in
      pytest) green on both engines.
- [ ] Autogenerate-drift test (compare metadata vs migrations, empty diff) green.
- [ ] All constraint tests pass on sqlite and (in CI) Postgres.
- [ ] WAL + foreign_keys pragmas verified by test on sqlite connections.
- [ ] `glyphlab-service-migrate` exists and upgrades a fresh sqlite file.

# Validation

```bash
uv run pytest packages/service/tests/db -q          # includes cycle + drift tests
TEST_POSTGRES_URL=... uv run pytest packages/service/tests/db -q   # when Postgres available
GLYPHLAB_DATA_DIR=$(mktemp -d) uv run glyphlab-service-migrate && echo migrated
```

# Dependencies

26.

# Non-goals

Queue claim logic (32), retention sweeps (36), any endpoint.

# Design References

DESIGN §14.2, §14.4 (tombstones), ADR-005 (dual-engine requirement).

# glyphlab service

The private FastAPI package orchestrates the shared core through isolated spawned
processes. Run exactly one web process; SQLite/LocalDiskStore is the default.

From the workspace root:

```bash
uv sync --all-packages --extra test --extra qa --extra postgres
export GLYPHLAB_DATA_DIR="$PWD/.data"
uv run glyphlab-service-migrate
uv run glyphlab-service
```

`glyphlab-service` does not implicitly migrate. The container entrypoint
`python -m glyphlab_service.entry` runs the migration command before starting one
Uvicorn process. Production disables interactive API documentation; the contract
remains at `/api/openapi.json`. `/healthz` checks DB connectivity and object storage.

Project tokens appear only in the create response. Send them through the Bearer
Authorization header. Unknown projects and invalid credentials return the same
404 envelope before request-body validation. No account recovery or public
artifact links exist. The service does not accept custom charsets or external
URLs. Upload image decoding and native tracing run in a child with a hard timeout.

The worker protects accepted glyphs again when applying a result, discards results
from superseded attempts, removes original images on terminal ingest states, and
keeps the latest three builds. QA failures retain their four artifacts for
inspection. Project deletion and retention purge the object prefix before deleting
rows; failed purges are retried. PostgreSQL supports the same schema and queue
claim behavior. S3 support uses the same structured key model and proxies downloads
through the API.

## Validation

```bash
uv run pytest packages/service/tests -q
TEST_POSTGRES_URL=postgresql+psycopg://postgres:test@localhost:5432/postgres \
  uv run pytest packages/service/tests/db packages/service/tests/jobs/test_queue.py -q
uv run python -m glyphlab_service.export_openapi | diff - packages/service/openapi.json
uv run python -m glyphlab_service.export_openapi --error-codes
ABUSE_BASE_URL=http://localhost:8080 uv run pytest packages/service/tests/abuse -q
```

The PostgreSQL test database must be disposable: tests migrate down after each
case. The default suite includes native potrace, a real generated scan, real
FontBakery QA, private downloads, accepted-glyph re-ingest, both storage backends
(S3 via moto), lease contention, process timeout/crash, retention, and schema/abuse
checks. `ABUSE_BASE_URL` runs the HTTP-only subset against a live service and skips
checks requiring in-process injection. Default production rate limits remain
active in that mode; use a clean instance for the small subset.

Rate limits are in-memory and project locks assume one application process.
`GLYPHLAB_TRUST_PROXY_HEADERS=true` is safe only behind a trusted proxy that
replaces client-supplied forwarding headers. Self-hosting leaves it false. Disk
pressure is checked by the sweeper; the S3 backend relies on project quotas and
operator-side bucket monitoring. See the deployment runbook for HTTPS, storage,
retention, and operational configuration.

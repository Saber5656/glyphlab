# Title

Service scaffold: FastAPI app factory, settings, health, error envelope, logging

# Summary

Bootstrap `glyphlab-service`: application factory, pydantic-settings configuration
(`GLYPHLAB_*` env), `/healthz` + `/meta`, the §15 error envelope wired to the §22 registry,
request-ID middleware, and the token-redacting structured logger.

# Context

Every service issue builds on these conventions; the logging policy (no tokens, no filenames,
no image bytes — §17.3 T3) must exist before any endpoint does.

# Scope

`packages/service/src/glyphlab_service/{app.py,settings.py,logging.py,errors.py}` + tests.
Adds service deps: `fastapi`, `uvicorn`, `pydantic-settings`.

# Detailed Requirements

1. `settings.py`: `Settings(BaseSettings)` with `env_prefix="GLYPHLAB_"`: `data_dir: Path =
   "/data"`, `database_url: str = ""` (empty → sqlite at `{data_dir}/glyphlab.db`),
   `object_store: Literal["local","s3"] = "local"`, S3 fields (endpoint, bucket, region,
   access key id — secret via env only), `retention_days: int = 14`, `public_base_url: str
   = ""`, `environment: Literal["dev","prod"] = "prod"`, and the exact limit/knob fields
   consumed by later issues (all env-overridable):
   `trust_proxy_headers: bool` (default = environment == "prod"),
   `cors_dev_origin: str = "http://localhost:5173"`,
   `max_upload_bytes: int = 12 * 2**20`, `max_upload_request_bytes: int = 13 * 2**20`,
   `max_json_body_bytes: int = 65536`, `max_uploads_per_project: int = 40`,
   `max_project_storage_bytes: int = 100 * 2**20`, `max_queued_jobs_per_project: int = 5`,
   `max_store_bytes: int = 5 * 2**30`, `job_concurrency: int = 1`,
   `job_timeout_s: int = 150`, `sweep_interval_s: int = 3600`,
   `rl_create_per_minute: int = 3`, `rl_create_per_day: int = 10`,
   `rl_uploads_per_hour_ip: int = 40`, `rl_uploads_per_hour_project: int = 20`,
   `rl_builds_per_hour_project: int = 10`, `rl_default_per_minute: int = 120`;
   S3 fields exactly: `s3_endpoint_url: str = ""`, `s3_bucket: str = ""`,
   `s3_region: str = ""`, `s3_access_key_id: str = ""`,
   `s3_secret_access_key: str = ""`; `webui_dist: Path = Path("/app/webui-dist")`.
   Masking (§17.3 T11): `__repr__`/`model_dump` replace with `"[masked]"` every field
   matching `(secret|key|password)` **plus** `database_url` (it can embed credentials) —
   unit test asserts each masked field. App state also carries
   `app.state.storage_pressure: bool = False` (set by issue 36, read by issue 31).
2. `app.py`: `create_app(settings) -> FastAPI` — `docs_url=None, redoc_url=None` in prod
   (OpenAPI JSON still served at `/api/openapi.json`; UI consoles off), routers registered
   under `/api`, SPA static mount at `/` from `settings.webui_dist` **only if the
   directory exists** (any environment; absent → log a warning and serve API only — the
   Acceptance boot without a webui build must succeed), lifespan hook stubs for
   worker/sweeper (filled by 32/36).
3. `errors.py`: exception handlers — `GlyphlabError` → JSON envelope
   `{"error": {"code", "message", "detail"}}` with `ERROR_REGISTRY[code].http_status`;
   `RequestValidationError` → 422 `E_VALIDATION` with field detail; catch-all → 500
   `E_INTERNAL` (no stack traces in body; logged with request id).
4. `logging.py`: stdlib logging JSON formatter: `ts, level, logger, msg, request_id,
   project_id?, job_id?, error_code?`; a redaction filter that replaces values of keys
   matching `(authorization|token|secret|filename)` (case-insensitive) with
   `"[redacted]"` anywhere in the record args; module docstring states the §19 policy —
   log records must never carry tokens, client filenames, or image bytes (later issues'
   log calls pass sizes/hashes instead); concise access log middleware (method,
   path-with-ids-templated, status, ms) replacing uvicorn's (`access_log=False`).
5. Endpoints: `GET /healthz` → 200 `{"ok": true}` doing a DB ping + store write-probe once
   wired (until 27/28 land: static ok — leave TODO markers referenced by those issues);
   `GET /api/meta` → `{version, retention_days, charsets: [{id, version, encoded, drawn,
   pages}]}` — `pages` via core `compute_layout` (issue 07; hence the 04/07 dependency),
   the rest from presets + settings (§15).
6. Request-ID middleware: honor inbound `X-Request-Id` (sanitized `[A-Za-z0-9\-]{1,64}`)
   else uuid4; echo header; bind into logging context (contextvar).
7. Tests: httpx TestClient — meta values exact for ja-basic-v1 (encoded 278, drawn 276,
   pages 6); error envelope for a route that raises each error class (test-only route in
   `environment="dev"`); prod-mode 500 path: build the app with `environment="prod"` and
   a monkeypatched route dependency that raises `RuntimeError` → body is the §15 envelope
   with `E_INTERNAL` and contains no `Traceback`/file-path strings; redaction filter unit
   test; settings masking test.

# Acceptance Criteria

- [ ] `uvicorn glyphlab_service.app:create_app_prod` boots with only `GLYPHLAB_DATA_DIR`
      set (factory helper reading env).
- [ ] Envelope shape matches §15 for 4xx/5xx; no traceback bodies in prod mode.
- [ ] Log lines are valid JSON; a request with `Authorization: Bearer x` never logs `x`
      (grep test on captured logs).
- [ ] `/api/meta` charset numbers match issue-04 presets.

# Validation

```bash
uv run pytest packages/service/tests/test_scaffold.py -q
GLYPHLAB_DATA_DIR=$(mktemp -d) uv run uvicorn --factory glyphlab_service.app:create_app_prod --port 8080 &
UV_PID=$!
for i in $(seq 1 20); do curl -sf localhost:8080/healthz && break; sleep 0.5; done
curl -s localhost:8080/api/meta | python3 -m json.tool | head
kill $UV_PID
```

# Dependencies

01, 04 (presets), 06 (registry), 07 (`compute_layout` for meta pages).

# Non-goals

DB (27), storage (28), auth (29), rate limits/headers (35), worker (32).

# Design References

DESIGN §14.1, §15 (envelope, meta), §17.3 T3, §19 (observability), §22.

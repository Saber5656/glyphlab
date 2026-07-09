# Title

Upload endpoint: validation, quotas, job enqueue

# Summary

Implement `POST /api/projects/{id}/uploads`: size-capped multipart intake, magic-byte
validation (reusing core S1 checks), per-project quotas, upload persistence, and ingest-job
enqueue returning `202 {upload_id, job_id}`.

# Context

The single place untrusted binary content enters the hosted service (§17.3 T1, T4). Fast
request-path checks here; heavy parsing stays in the worker (32).

# Scope

`packages/service/src/glyphlab_service/api/uploads.py` + quota helpers + tests. Adds service
dep: `python-multipart`.

# Detailed Requirements

1. Route `POST /api/projects/{id}/uploads`, multipart field `file` (exactly one):
   - Byte-cap enforcement is layered (per §17.4): (a) issue 35's pre-routing
     Content-Length wall at `settings.max_upload_request_bytes` (13 MiB); (b)
     python-multipart spools parts to disk (never unbounded memory); (c) an explicit
     chunked copy from the spooled `UploadFile` counts bytes and aborts at
     `settings.max_upload_bytes` (12 MiB) + 1 → `E_IMG_TOO_LARGE` 413, temp file deleted.
     Tests must prove `UploadFile.read()` (full-file form) is never called (monkeypatch it
     to raise).
   - Magic-byte sniff via issue 10's `sniff_format` on the first 32 bytes → `None` →
     `E_IMG_FORMAT` 415. (Deep validation happens in the worker; a crafted polyglot with a
     valid image magic passes this check by design and fails at decode/ingest.)
   - Global storage pressure: `app.state.storage_pressure` (set by issue 36's sweeper;
     False until then) → 507 `E_QUOTA_EXCEEDED` detail `{"limit": "global"}`.
   - Quotas (checked in one transaction, limits from Settings — issue 26 field names):
     uploads count < `max_uploads_per_project` (`E_QUOTA_EXCEEDED` 409, detail
     `{"limit": "uploads", "max": N}`); Σ`uploads.bytes` + new ≤
     `max_project_storage_bytes` → same code, `{"limit": "storage"}`; **queued** jobs for
     the project < `max_queued_jobs_per_project` (§14.3 — queued only, running excluded)
     → `E_RATE_LIMITED` 429.
   - Persist: sha256 while streaming; duplicate sha256 for the project → **200** with the
     existing ids: `{upload_id, job_id, deduplicated: true}` (§15 documents 200 and 202
     variants; OpenAPI declares both).
   - Store bytes via issue 28's `StoreKey(project_id, "uploads", name=<upload_id hex>)`;
     insert `uploads` row (status `received`) + `jobs` row (type `ingest`, payload
     `{"upload_id": ...}`, status `queued`) atomically; **202** response
     `{upload_id, job_id, deduplicated: false}`.
2. Content-Length precheck: header > cap → 413 before reading body (belt to 35's braces).
3. No image decode on the request path (decode happens in the worker under job timeout).
4. Tests: happy path (202, rows, stored bytes match sha); 13 MiB body cut off at cap
   without memory blowup (RSS smoke); zip-renamed-to-png (magic `PK`) rejected 415;
   polyglot with valid JPEG magic ACCEPTED here (documented; fails later at ingest);
   41st upload 409; storage_pressure flag → 507; duplicate content → 200 dedup body;
   missing/extra multipart fields → 422; wrong token → 404; `UploadFile.read` never
   called.

# Acceptance Criteria

- [ ] Cap enforced by observed bytes-read, not header trust (test with lying
      Content-Length).
- [ ] All quota branches covered (project uploads/storage/queue + global 507); limits read
      from the exact Settings fields of issue 26.
- [ ] `UploadFile.read` monkeypatch test proves streaming-only handling.
- [ ] Dedup path returns 200 with the original ids and creates no new rows.

# Validation

```bash
uv run pytest packages/service/tests/api/test_uploads.py -q
```

# Dependencies

10 (sniffer export), 28, 29.

# Non-goals

Actual ingest execution (32), rate limiting middleware (35 — per-IP layer on top), virus
scanning (out of scope; formats are raster-only and re-encoded downstream).

# Design References

DESIGN §15, §17.3 T1/T4, §17.4 (upload rules), §14.2 (uploads/jobs), §14.3 (queue caps).

# Title

OpenAPI contract pinning & schemathesis property tests

# Summary

Export the FastAPI-generated OpenAPI spec to a committed `packages/service/openapi.json`,
fail CI on drift, and run schemathesis against the app to fuzz every endpoint for
contract/robustness violations — per DESIGN §15's contract-pinning rule.

# Context

The web UI's typed client (39) is generated from the committed spec; pinning turns silent
API drift into a loud diff. Schemathesis additionally shakes out 500s from malformed inputs
the hand-written tests missed.

# Scope

Spec export script + CI wiring + schemathesis test module. Adds dev dep: `schemathesis`.

# Detailed Requirements

1. Export: `uv run python -m glyphlab_service.export_openapi > packages/service/openapi.json`
   — module renders `create_app(dev_settings).openapi()` with deterministic key order
   (sorted, 2-space indent, trailing newline). All §15 routes must carry typed request/
   response models (fix any endpoint returning bare dicts — response_model everywhere).
   `operationId`s, exact table (hygiene test asserts it):
   `create_project, get_project, delete_project, get_template_pdf, create_upload,
   get_job, list_glyphs, get_glyph_svg, review_glyphs, create_build, list_artifacts,
   download_artifact, get_meta, healthz`.
   Security scheme: components declare `bearerAuth` (http bearer); every operation except
   `create_project`, `get_meta`, `healthz` references it.
2. Error responses documented per route from the owning issues' specs (29–36), all
   referencing one shared `ErrorResponse` component: every authenticated route declares
   404; uploads adds 409/413/415/429/507; builds adds 409/422/429; review adds 422;
   everything may return 500. (The §22 table gives the code↔status mapping; the §15 table
   documents 2xx shapes.)
2b. Same module exports the error-code list consumed by the webui:
   `uv run python -m glyphlab_service.export_openapi --error-codes >
   webui/src/generated/error-codes.json` — a JSON array of §22 code strings; committed,
   drift-checked in CI alongside the spec (issue 39 consumes it).
3. CI check (extend `ci.yml`): regenerate spec in the job and `git diff --exit-code
   packages/service/openapi.json` — drift fails with a message telling the agent to re-run
   the export script and review the diff.
4. Schemathesis module `packages/service/tests/test_contract.py`: run against an
   in-process app (ASGI transport). Stateful-fixture strategy (spelled out so nothing is
   guessed): a session fixture creates one project via the real API and performs one
   upload + one build with corpus fixtures, then exposes `{project_id, token, job_id,
   artifact_id}`; a schemathesis `before_call` hook injects the Authorization header and
   substitutes these known-good ids for path parameters (while ALSO letting schemathesis
   fuzz them raw in a second unauthenticated pass). Profile `max_examples=50` per
   operation in PR CI. Checks: no 5xx ever; responses validate against the spec;
   missing, malformed, wrong-token, wrong-id, expired, and otherwise tokenless calls on secured
   operations → the uniform issue-29 404 body, never 2xx and never FastAPI validation 422.
   Exclusions: artifact binary downloads checked for status codes only.
5. Spec hygiene assertions (unit): every path starts `/api/` (except `/healthz`); every
   operation has `operationId`; no endpoint exposes `token` in a URL parameter; ErrorResponse
   referenced by ≥ 90% of operations.

# Acceptance Criteria

- [ ] Committed spec + error-codes.json match generated output (CI drift check green on
      the introducing PR; verifiable locally via the Validation diff commands).
- [ ] Schemathesis run green (zero 5xx, zero schema violations) on the full API.
- [ ] operationId set equals the req-1 table exactly; `bearerAuth` on all secured
      operations (hygiene test).
- [ ] Drift-check negative test: `git stash`-able scratch edit to a response model makes
      the local diff command fail (documented in PR description, not committed).

# Validation

```bash
uv run python -m glyphlab_service.export_openapi | diff - packages/service/openapi.json
uv run python -m glyphlab_service.export_openapi --error-codes | diff - webui/src/generated/error-codes.json
uv run pytest packages/service/tests/test_contract.py -q
```

# Dependencies

29, 30, 31, 32, 33, 34, 35, 36 (all routes exist).

# Non-goals

Client generation itself (39), versioned public API stability guarantees (v1 is
pre-stability; the pin is an internal contract).

# Design References

DESIGN §15 (contract pinning paragraph, envelope), §18.1 (Service API row), §22 (status
mapping).

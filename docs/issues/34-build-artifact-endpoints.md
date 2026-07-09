# Title

Build trigger & artifact endpoints

# Summary

Implement `POST /api/projects/{id}/builds` (enqueue build job with single-flight guard),
`GET /api/projects/{id}/artifacts` (list), and `GET /api/projects/{id}/artifacts/{artifact_id}`
(streamed, token-guarded download) per DESIGN §15.

# Context

Font delivery is the product's payoff; downloads stay behind the project token (no public
URLs, §17.3 T8) and stream through the app (ADR-005: no presigned URLs in v1).

# Scope

`packages/service/src/glyphlab_service/api/{builds.py,artifacts.py}` + tests.

# Detailed Requirements

1. `POST /builds`: atomically (same advisory-lock pattern as issue 30 — lock the project
   row, then check-and-insert in one transaction, so a race cannot enqueue two builds):
   if a `build` job exists with status queued|running → 409 `E_BUILD_IN_PROGRESS` with
   `detail = {"job_id": "<running job uuid>"}` (issue 43 resumes polling from it); if
   zero glyphs in status accepted|auto → 422 `E_VALIDATION`
   `detail = {"reason": "nothing_to_build"}`; else insert job (payload `{}`) → 202
   `{job_id}`. (Build rate limiting layered in 35.)
2. `GET /artifacts`: **build outputs only** — kinds ttf/woff2/proof_html/qa_json;
   `template_pdf`/`template_sidecar` are never listed (§15) — ordered `created_at desc`;
   each `{id, kind, job_id, bytes, sha256, created_at}` (§15 shape; `job_id` groups one
   build's four artifacts — issue 43 renders history with it). Multiple builds accumulate;
   the newest set is first (old artifacts pruned to ≤ 3 builds post-build in the 32
   handler; assert here it is reflected).
3. `GET /artifacts/{artifact_id}`:
   - UUID-parse artifact id (422 on garbage); row must belong to the authed project (T12).
   - `template_pdf` and `template_sidecar` rows → uniform 404 (internal/off-route kinds;
     the template PDF is served only by issue 30's dedicated endpoint).
   - Stream via `store.stream`; headers by kind (hosted font version is fixed at 1 — §15):
     ttf → `font/ttf` + `Content-Disposition: attachment; filename="{family}-v1.ttf"`
     (family from the project row — §10.4-validated ASCII, safe for a quoted filename);
     woff2 → `font/woff2` attachment (same naming); qa_json → `application/json`
     attachment `qa-report.json`; proof_html → `text/html; charset=utf-8` **inline**
     (self-contained per §11.3) + `Content-Security-Policy: sandbox` + nosniff.
   - `Content-Length` from row bytes; `Cache-Control: private, no-store`.
4. Tests: single-flight 409 incl. `detail.job_id` and a two-concurrent-requests race
   (exactly one job row); empty-project 422 with `detail.reason`; kind→header matrix
   exact (parametrized, incl. both template kinds → 404); cross-project artifact id →
   404; stream content sha matches row sha256; listing excludes template kinds; latest-3
   pruning reflected in listing (with 32 integration fixture).

# Acceptance Criteria

- [ ] Download bytes byte-identical to stored artifact (sha check in test).
- [ ] Header matrix exact for all kinds incl. proof_html sandbox+nosniff.
- [ ] `E_BUILD_IN_PROGRESS` and nothing-to-build paths covered.
- [ ] No presigned/tokenless access path exists (grep-level review note in PR).

# Validation

```bash
uv run pytest packages/service/tests/api/test_builds_artifacts.py -q
```

# Dependencies

29, 32.

# Non-goals

Public sharing links (v2 decision), artifact retention beyond latest-3 (36 handles project
TTL), font subsetting endpoints.

# Design References

DESIGN §15, §17.3 T8/T12, §14.2 (artifact kinds), §11.3 (proof self-containment), §10.4
(family-name constraint).

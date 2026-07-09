# Title

Template PDF endpoint (artifact-cached)

# Summary

Serve `GET /api/projects/{id}/template.pdf`: generate the project's template PDF + sidecar on
first request (core issue 07/08), persist both as artifacts, and stream the PDF on subsequent
requests.

# Context

Hosted users download the template from here; the sidecar stored server-side is what ingest
jobs (32) use to map cells — it must be the exact sibling of the served PDF.

# Scope

`packages/service/src/glyphlab_service/api/template.py` + tests.

# Detailed Requirements

1. Route `GET /api/projects/{id}/template.pdf` (auth via 29 dependency):
   - If artifacts of kind `template_pdf` exist → stream from store with
     `Content-Type: application/pdf`, `Content-Disposition: attachment;
     filename="glyphlab-template-{charset_id}.pdf"` (ASCII-only filename — no user input in
     header), `Cache-Control: private, max-age=3600`.
   - Else generate synchronously (budget §21 ≤ 5 s — acceptable inline; no job): call
     issue 08's `generate_template(out_dir=<tempdir>, charset=<project charset>,
     template_id=<projects.template_id>, project_name=<projects.name>)` (name flows
     through 08's §7.3 sanitizer); persist both outputs per §14.2 — PDF as kind
     `template_pdf` (content type `application/pdf`) and sidecar as kind
     `template_sidecar` (`application/json`; internal-only kind, issue 34's download route
     must never serve it) — storage keys are server-minted UUID names via issue 28's
     `StoreKey(category="artifacts")`, artifact rows record bytes + sha256 computed while
     writing.
   - Generation is idempotent-guarded by a per-project advisory lock (SELECT ... FOR UPDATE
     on the project row / sqlite immediate transaction) so concurrent first-requests build
     once.
2. Internal accessor `get_sidecar(session, store, project) -> TemplateSidecar` (used by
   32): if the `template_sidecar` artifact is missing (upload arrived before any template
   download — allowed by 31), generate-and-persist first via the same idempotent-locked
   path as req 1; corrupt/unparseable stored sidecar → `E_INTERNAL` (log; do not
   regenerate silently — template_id integrity); multiple rows cannot exist (unique
   partial index on `artifacts(project_id, kind)` for the two template kinds — add in the
   migration).
3. Tests: first call generates + persists (2 artifacts rows with bytes/sha256), second
   call streams without calling the generator (spy); concurrent double-request builds
   once; auth matrix (tokenless / malformed / wrong token / cross-project token) →
   uniform 404 (T12/T3); headers exact; response never contains the token; sidecar loads
   via core reader and matches project charset; `get_sidecar` on a template-less project
   generates it; XSS-bearing project name renders no unsanitized bytes into headers
   (filename is fixed ASCII).

# Acceptance Criteria

- [ ] PDF streams with exact headers; body parses as PDF (`%PDF-` magic).
- [ ] Exactly one generation under concurrency test.
- [ ] Sidecar persisted as kind `template_sidecar`; `get_sidecar` round-trips via the core
      reader.
- [ ] No user-controlled bytes in response headers.

# Validation

```bash
uv run pytest packages/service/tests/api/test_template.py -q
```

# Dependencies

07, 08, 28, 29.

# Non-goals

Regeneration endpoint (v1: template fixed per project — charset is immutable after create),
ingest (31/32).

# Design References

DESIGN §15 (endpoint table), §14.2 (artifact kinds incl. template_sidecar), §7.3 (name
sanitizing), §17.3 T3/T12, §21.

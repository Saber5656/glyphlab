# Title

Token auth & project endpoints: create, get, delete

# Summary

Implement the anonymous-token security core (ADR-002) and the first real endpoints:
`POST /api/projects` (mint token), `GET /api/projects/{id}`, `DELETE /api/projects/{id}`,
with the uniform-404 policy and last-access touching.

# Context

Every other authenticated endpoint reuses the dependency built here. Token handling rules
(§15, §17.3 T2/T3/T12) are exact and non-negotiable.

# Scope

`packages/service/src/glyphlab_service/{auth.py,purge.py,api/projects.py}` + glyph-row
seeding + tests.

# Detailed Requirements

1. Token mint (create only): `raw = secrets.token_bytes(32)`; `token = "glp_" +
   base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")` (47 chars total); store
   `hashlib.sha256(token.encode("ascii")).digest()` (32 bytes) in `projects.token_hash`.
   The token appears in the 201 response body once — the ONLY place it ever appears — and
   is never persisted in clear, never logged (26's redaction as backstop), never put in
   any URL.
2. Auth dependency `require_project(project_id: UUID, authorization: Header) -> Project`:
   - Parse `Bearer glp_...` (strict prefix); compute sha256; SELECT the project row by
     `id` alone, then compare digests with `hmac.compare_digest(row.token_hash, digest)`
     (constant-time; comparing in Python rather than in the WHERE clause is what makes the
     wrong-token and unknown-id paths do the same work). Any miss (no row OR digest
     mismatch) → `E_NOT_FOUND` 404 with an identical body.
   - Expired project (`expires_at < now`) → also uniform 404 (data may still await sweep).
   - Touch `last_accessed_at` (and recompute `expires_at`) at most once per hour
     (UPDATE ... WHERE last_accessed_at < now-1h).
3. `POST /api/projects` (unauthenticated, hard rate-limited in 35): body `{name,
   family_name, charset_id}` validated by §17.4 rules (reuse core validators from issue
   05's pydantic pieces — factor shared validators into `glyphlab.project.config`);
   creates the project row + seeds `glyphs` rows with status `missing` for **drawn
   charset codepoints only** (synthesized chars get no row — they exist only at font
   build); template_id minted (template artifact lazily built by 30). Response 201,
   exactly: `{"project_id": uuid, "token": "glp_…", "name": str, "family_name": str,
   "charset": {"id": str, "version": int, "encoded": int, "drawn": int},
   "template_pages": int (from compute_layout), "retention_days": int,
   "expires_at": iso8601}`.
4. `GET /api/projects/{id}` → 200, exactly: `{"project_id", "name", "family_name",
   "charset": {as above}, "counts": {"missing": int, "auto": int, "accepted": int,
   "rejected": int} (one GROUP BY over glyphs), "expires_at": iso8601}`.
5. `DELETE /api/projects/{id}`: synchronous purge via
   `glyphlab_service.purge.purge_project(session, store, project_id)` (defined HERE; the
   sweeper, issue 36, imports it): delete store prefix → delete rows (cascade) → insert
   tombstone; 204. The `store` is injected via the app-state `ObjectStore` (issue 28 —
   added to this issue's dependencies).
6. Tests: mint format/entropy (prefix, length, urlsafe); auth matrix (no header, malformed,
   wrong token, wrong id, expired) → all identical 404 bodies; touch throttling; create
   seeds exactly drawn-glyph rows; delete purges store objects (fake store spy) + rows +
   tombstone; charset_id unknown → 422 `E_VALIDATION`.

# Acceptance Criteria

- [ ] Auth matrix test proves body-identical 404s; the token string appears in exactly
      one response ever: the 201 create body (asserted by grepping all captured responses
      in the test suite).
- [ ] Timing: wrong-id vs wrong-token median delta < 20% in a 200-iteration micro-benchmark
      (loose smoke, marked flaky-tolerant, documents the intent).
- [ ] Created token authenticates immediately; second GET within the hour doesn't rewrite
      `last_accessed_at`.
- [ ] No route logs contain `glp_` (log-capture grep test).

# Validation

```bash
uv run pytest packages/service/tests/api/test_projects.py -q
```

# Dependencies

26, 27, 28 (ObjectStore for purge).

# Non-goals

Rate limiting itself (35), template generation (30), retention scheduling (36 — shares
`purge_project`).

# Design References

DESIGN §15 (endpoints, token spec), §17.3 T2/T3/T12, §14.4, ADR-002.

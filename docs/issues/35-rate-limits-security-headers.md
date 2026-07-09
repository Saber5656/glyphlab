# Title

Rate limiting & security headers middleware

# Summary

Add the cross-cutting HTTP protections of DESIGN §17.5–§17.6: slowapi rate limits per
scope/IP/project, global request-size guard, the security-header set, and the CORS posture
(same-origin prod, explicit dev allowlist).

# Context

These controls close T2 (brute force) and T4 (abuse volume) at the request layer,
composing with the per-endpoint quotas of issue 31 (T5's compute controls live in the
worker/tracer, not here). They must be on by default — secure defaults are a v1 goal (G8).

# Scope

`packages/service/src/glyphlab_service/limits.py` + app wiring in `app.py` + tests. Adds
service dep: `slowapi`.

# Detailed Requirements

1. Client IP resolution (`limits.py::client_ip(request) -> str`), security-sensitive and
   exactly specified: when `settings.trust_proxy_headers` (issue 26 field; default =
   prod) is False → always the socket peer. When True: use `Fly-Client-IP` if present and
   a valid IP literal; else if `X-Forwarded-For` present take its **last** entry (the hop
   appended by the trusted platform proxy — earlier entries are client-forgeable); else
   socket peer. Invalid/unparseable values → socket peer. Deployment assumption documented
   in the module docstring: trust_proxy_headers=True is only safe behind a proxy that
   overwrites these headers (Fly does — research/03).
2. slowapi limiter with in-memory storage (single instance per ADR-005; note in code that
   D7 multi-instance needs a shared store):
   - `POST /api/projects`: `3/minute` and `10/day` per IP.
   - `POST .../uploads`: `40/hour` per IP + `20/hour` per project (project key = path id
     after auth — implement as a dependency-based check, slowapi keyed on
     `f"proj:{id}"`).
   - `POST .../builds`: `10/hour` per project.
   - Default for all **authenticated** routes (`/api/projects/{id}/**`): `120/minute` per
     IP (§17.6 "any authenticated"). Explicitly excluded: `POST /api/projects` (has its
     own stricter rule), `GET /api/meta`, `GET /api/openapi.json`, `/healthz`.
   - 429 responses use the §15 envelope `E_RATE_LIMITED` + `Retry-After`.
   - All six rates read from issue 26's `rl_*` settings fields.
3. Request-size guard middleware (pre-routing), two explicit tiers keyed on the route:
   `POST */uploads` → `settings.max_upload_request_bytes` (13 MiB); every other route →
   `settings.max_json_body_bytes` (64 KiB). POST/PUT/PATCH without a Content-Length header
   → 411. Over-cap → 413 with envelope code `E_REQUEST_TOO_LARGE` (§22; the uploads
   route's own deeper cap still answers `E_IMG_TOO_LARGE` for oversized *files* that fit
   the request wall).
4. Security headers middleware: exactly the §17.5 canonical set (nosniff,
   Referrer-Policy, Permissions-Policy, COOP, CORP, HTML-CSP vs API-JSON-CSP; HSTS left to
   the PaaS proxy, documented). Middleware sets each header only when absent so that
   route-level CSPs win — issues 33/34 land later and their SVG/proof overrides must
   survive unchanged (forward contract; no dependency edge).
5. Abuse-event recording (§17.7/§14.2): every 429 emitted here inserts an `abuse_events`
   row (`kind="rate_limited"`, client ip); issue 29's auth misses insert
   `kind="auth_miss"` (that write is added here as a small patch to the auth dependency
   if 29 is already merged). Rows are trimmed by issue 36's sweeper (7 days).
6. CORS: prod → no CORS middleware at all (same-origin SPA); `settings.environment ==
   "dev"` → `CORSMiddleware` allowing `settings.cors_dev_origin` with credentials disabled
   and `Authorization` header allowed.
7. Tests: each limit trips at its boundary (freeze/loop with distinct IPs via header
   injection under trust_proxy_headers=True); envelope + Retry-After on 429; header
   presence on 200/404/429 responses; set-if-absent behavior (a route that pre-sets CSP
   keeps it); 64 KiB JSON wall (`E_REQUEST_TOO_LARGE`) + 411 path; IP resolution matrix
   (trust off → spoofed XFF ignored; trust on → Fly-Client-IP wins over XFF; garbage
   header → socket peer); abuse_events rows written on 429.

# Acceptance Criteria

- [ ] All six limit rules enforced with boundary tests, reading `rl_*` settings.
- [ ] Header set present on every response class; set-if-absent proven.
- [ ] IP-resolution matrix proven (both trust modes, precedence, garbage handling).
- [ ] Size walls: 413 `E_REQUEST_TOO_LARGE` (64 KiB tier) and 411 paths covered.
- [ ] `abuse_events` written on 429 and on auth miss.

# Validation

```bash
uv run pytest packages/service/tests/test_limits_headers.py -q
```

# Dependencies

26, 29 (auth/project keys for per-project limiter keys and the auth-miss event patch).

# Non-goals

WAF/bot detection, distributed rate-limit stores (D7), captcha.

# Design References

DESIGN §17.5, §17.6, §17.3 T2/T4, §17.7 (abuse events), §14.2 (abuse_events table), §15
(envelope), §22 (`E_REQUEST_TOO_LARGE`), research/03 (proxy headers).

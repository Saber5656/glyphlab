# Title

Security abuse regression suite (threat-model T1–T12)

# Summary

One test module per DESIGN §17.3 threat row: executable attacks that must stay defeated.
This suite is the standing proof that the threat model's mitigations exist and keep
existing; it runs on every PR (§18.1 security layer).

# Context

Individual issues implement controls; this issue adversarially exercises them end-to-end
through the public API surface, so a future refactor cannot silently drop one.

# Scope

`packages/service/tests/abuse/` (test-only). Fixtures may reuse corpus/malicious files
from earlier issues; crafted payloads live under
`packages/service/tests/abuse/payloads/`. The suite runs in TWO modes sharing test code
via a client fixture: in-process (default; ASGI TestClient, monkeypatching allowed) and
container mode (`ABUSE_BASE_URL=http://...` env → tests marked `requires_inprocess` are
skipped; issue 49 runs this API-level subset against the real container).

# Detailed Requirements

Implement at minimum (test name ↔ threat):

1. `test_t1_decompression_bomb`: 100k×100k PNG-header upload — passes the sniff (valid
   PNG magic) so it is ACCEPTED at upload and must fail in the worker with
   `E_IMG_TOO_LARGE` (job `failed`; §8.2 S1 header probe); web-process RSS sampled around
   the request stays < 300 MiB (§21 web ceiling; psutil, in-process mode only).
2. `test_t1_polyglot`: zip-with-PNG-magic, truncated JPEG, SVG-renamed-jpg → all rejected
   at upload or fail ingest with clean `E_IMG_*` (no traceback leakage in envelope).
3. `test_t2_token_bruteforce`: 50 random tokens against a real project id → uniform 404
   bodies; then per-IP limiter trips at 120/min with 429.
4. `test_t3_no_token_leak`: exercise create/upload/error paths with log capture → grep
   captured logs and all response bodies for `glp_` → only the single create response
   contains it.
5. `test_t4_quota_walls`: 41st upload 409; 101 MiB cumulative 409; queue-cap 429; global
   watermark 507 (flag injection); project-creation limit trips at 10/day per IP (T4's
   creation wall — freeze clock, 11th create → 429).
6. `test_t5_trace_bomb`: adversarial noise page (1-px checkerboard cells) as a crafted
   upload → ingest job terminates ≤ its timeout with failed-or-succeeded (no hang; assert
   wall time) AND the report shows checker cells `failed` via issue 12's 64-component cap
   (never traced); potrace 10 s kill covered at engine level (13) — here assert only the
   end-to-end bound.
7. `test_t6_traversal`: upload filename `../../../etc/passwd`, glyph cp `U+0041%2F..%2F`,
   artifact id `../secrets` → 404/422; assert no file outside the store root was created
   (walk tmp store).
8. `test_t7_xss_names`: project name `<img src=x onerror=alert(1)>` flows through create →
   proof build → artifact download: proof HTML contains it only escaped; SVG/proof
   responses carry nosniff+CSP headers.
9. `test_t8_no_public_artifacts`: artifact URL without token → 404; another project's
   token → 404.
10. `test_t9_no_egress`: monkeypatch-socket guard asserting the app makes zero outbound
    network connections during a full journey (allowlist: DB/store endpoints under test
    config).
11. `test_t12_cross_project`: two projects; every mutating endpoint called with A's id +
    B's token → uniform 404; B's state unchanged (deep-compare).
12. `test_error_envelope_no_internals`: force an injected unexpected exception (dev-only
    route) → 500 envelope has no traceback/path strings.

Also: `test_t10_t11_repo_guards` (the in-repo mirror of issue 03's CI coverage):
`uv.lock` and `webui/package-lock.json` exist and are tracked; `git ls-files` contains no
`.env*` or `*.pem`; `settings.py` masks secret-ish fields (imports the issue-26 unit
check).

Suite conventions: each test docstring cites its threat id; suite runs with
`trust_proxy_headers=true` and header-injected IPs to exercise limiter keying; wall-clock
budget ≤ 3 min in CI.

# Acceptance Criteria

- [ ] All tests green in in-process mode; container-mode subset green against the compose
      stack (`ABUSE_BASE_URL` smoke, run once in this issue's PR and again by issue 49).
- [ ] Each §17.3 row T1–T12 has ≥ 1 test naming it (docstring grep test enforces the
      mapping).
- [ ] Knockout check: with the upload size cap env-set to 10 GiB, `test_t4_quota_walls`
      fails (run locally, documented in PR description, not committed).
- [ ] Runs in PR CI within budget.

# Validation

```bash
uv run pytest packages/service/tests/abuse -q
```

# Dependencies

29, 31, 32, 33, 34, 35, 36.

# Non-goals

External pentest, DoS load testing at scale, fuzzing beyond schemathesis (37).

# Design References

DESIGN §17.3 (threat table — this suite is its executable mirror), §18.1, §18.3.

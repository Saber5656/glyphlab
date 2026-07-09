# Title

Web E2E: Playwright journeys against the docker-compose stack

# Summary

Automate the DESIGN §1.2 hosted user journey end-to-end in a real browser against the real
containerized service (issue 45's compose stack), including the error path — the Wave-6 exit
gate.

# Context

Unit/msw tests validate components against mocks; this issue validates the composed truth:
SPA ↔ API ↔ worker ↔ core pipeline ↔ storage, via the same image users self-host.

# Scope

`webui/e2e/` Playwright project + `ci.yml` job (`web-e2e`; per DESIGN §18.1 this layer
gates **push to main + workflow_dispatch**, not every PR). Uses corpus fixtures generated
at test setup.

# Detailed Requirements

1. Setup: `docker compose -f deploy/docker-compose.yml -f deploy/compose.e2e.yml up`
   (e2e override: **bind mount `./e2e-data:/data`** instead of the named volume, short
   retention + `GLYPHLAB_SWEEP_INTERVAL_S=5`, deterministic `SOURCE_DATE_EPOCH`); wait on
   `/healthz`. Corpus generation in Playwright's globalSetup (Python helper, available in
   CI): after creating the project and downloading template.pdf through the API, read the
   sidecar JSON **from the bind-mounted store** (`e2e-data/store/projects/<id>/artifacts/`
   — pick the JSON file whose `schema` field is `glyphlab.template/1`; the sidecar is
   internal-only over HTTP by design, §14.2) and call issue 09's
   `generate_corpus(template_pdf, sidecar, ...)`.
2. Journey spec (chromium + webkit; mobile viewport variant on chromium):
   a. Landing → create project (ja form) → token panel appears → copy link → assert
      localStorage.
   b. Template downloads (assert PDF magic bytes).
   c. Upload 2 corpus pages → progress → processed counts visible.
   d. Review: accept-all-AUTO → counts update.
   e. Build → wait for job → preview textarea shows custom font (assert
      `document.fonts.check("16px GlyphlabPreview")`) → download TTF (assert the file's
      sha256 equals the listing's `sha256` field, §15).
   f. Open project in a fresh context via the token link (fragment flow) → state intact;
      assert §16.2/T3 properties: after load `location.hash` is empty, and no request URL
      recorded by Playwright's network log contains `glp_`.
   g. Delete project → landing; token link now shows the invalid/expired screen.
3. Error-path spec: upload a blank white JPEG → `E_PAGE_NO_MARKERS` ja message + retry
   button visible; upload an oversized file → client precheck message (no network).
4. Flake policy: retries 1 in CI; every wait is event/condition-based (no bare sleeps);
   traces + video retained on failure as CI artifacts.
5. Runtime budget: ≤ 10 min in CI including image build (compose build cached via GH cache).

# Acceptance Criteria

- [ ] Both specs green on chromium + webkit + chromium-mobile (Validation runs all
      projects).
- [ ] Zero bare `waitForTimeout` calls (Validation grep).
- [ ] Failure artifacts (trace) uploaded on induced failure (verified once in the
      introducing run; documented in PR).
- [ ] Token-security assertions (fragment stripped, no `glp_` in request URLs) green.
- [ ] The journey uses only public UX surfaces (the sole exception: globalSetup reads the
      sidecar from the bind-mounted store for corpus generation).

# Validation

```bash
docker compose -f deploy/docker-compose.yml -f deploy/compose.e2e.yml up -d --build
cd webui && npx playwright test              # ALL specs × chromium/webkit/mobile projects
grep -rn "waitForTimeout" e2e/ && echo "FAIL: bare waits" || echo "no bare waits"
cd .. && docker compose -f deploy/docker-compose.yml -f deploy/compose.e2e.yml down -v
```

# Dependencies

40, 41, 42, 43, 45.

# Non-goals

Load testing, cross-browser matrix beyond chromium/webkit, visual regression snapshots
(v2 candidate).

# Design References

DESIGN §1.2 (journey), §18.1 (E2E layer), §18.3 (acceptance), ISSUE_PLAN §4 (W6 exit).

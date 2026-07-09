# glyphlab — v1 Issue Plan

- Status: canonical execution plan derived from `docs/DESIGN.md` (source of truth)
- Date: 2026-07-08
- Issue drafts: `docs/issues/NN-short-title.md` (English; GitHub Issues are derived from them)

## 1. v1 completion statement

**When every issue 01–49 below is completed and its Validation section passes, glyphlab v1 is
complete**: a user can print a charset template, handwrite it, and obtain a fontbakery-passing
TTF/WOFF2 of their handwriting either (a) fully locally via `glyphlab
new/template/ingest/status/build`, or (b) through the hosted web service (anonymous token
project, upload → review → build → download, 14-day retention), which the repository can build
and deploy as a hardened Docker image to Fly.io following `deploy/RUNBOOK.md` — with production
contracting/secrets remaining an explicitly human post-v1 task. Remaining risk is confined to
the known unknowns in §8.

## 2. Issue list (recommended execution order)

| # | File | Title | Wave |
|---|---|---|---|
| 01 | `01-monorepo-scaffolding.md` | Monorepo scaffolding: uv workspace, core package, tooling | W0 |
| 02 | `02-ci-lint-type-test.md` | CI: lint/type/test workflow | W0 |
| 03 | `03-ci-security-scanning.md` | CI: security scanning (pip-audit, bandit, gitleaks, pinned actions) | W0 |
| 04 | `04-charset-module.md` | Charset model & presets (ascii, kana, ja-basic-v1) | W0 |
| 05 | `05-project-config-local-store.md` | Project config schema & local project store | W0 |
| 06 | `06-core-domain-glyph-svg.md` | Core domain model, error registry, glyph SVG format (writer + restricted parser) | W0 |
| 07 | `07-template-layout-sidecar.md` | Template layout model & template.json sidecar | W1 |
| 08 | `08-template-pdf-renderer.md` | Template PDF renderer (reportlab + ArUco markers) | W1 |
| 09 | `09-synthetic-scan-corpus.md` | Synthetic scan corpus generator (test fixtures) | W1 |
| 10 | `10-image-decode-sanitize.md` | Ingest S1: image decode & sanitize | W2 |
| 11 | `11-page-detect-rectify.md` | Ingest S2–S4: marker detection, page id, rectification | W2 |
| 12 | `12-cell-slice-binarize.md` | Ingest S5–S8: cell slice, illumination, binarize, ink classify | W2 |
| 13 | `13-vectorizer-engines.md` | Vectorizer engines: potrace subprocess + potracer fallback | W2 |
| 14 | `14-path-cleanup-em-fitting.md` | Path cleanup & em-space fitting | W2 |
| 15 | `15-ingest-orchestrator.md` | Ingest orchestrator, report, re-ingest semantics | W2 |
| 16 | `16-font-assembly.md` | Font assembly: TTF + WOFF2 via fontTools | W3 |
| 17 | `17-font-qa-gate.md` | Font QA gate: fontbakery + structural self-checks | W3 |
| 18 | `18-html-proof-sheet.md` | HTML proof sheet generator | W3 |
| 19 | `19-cli-framework.md` | CLI framework: typer app, global flags, exit codes | W4 |
| 20 | `20-cli-new-charset.md` | CLI: `new`, `charset list/show` | W4 |
| 21 | `21-cli-template.md` | CLI: `template` | W4 |
| 22 | `22-cli-ingest.md` | CLI: `ingest` | W4 |
| 23 | `23-cli-status-review.md` | CLI: `status`, `accept`, `reject` | W4 |
| 24 | `24-cli-build.md` | CLI: `build` | W4 |
| 25 | `25-cli-e2e-golden.md` | CLI end-to-end golden test (corpus → font) | W4 |
| 26 | `26-service-scaffold.md` | Service scaffold: app factory, settings, health, error envelope, logging | W5 |
| 27 | `27-db-models-migrations.md` | DB models & Alembic migrations (SQLite + Postgres) | W5 |
| 28 | `28-object-store.md` | ObjectStore: local disk + S3 implementations | W5 |
| 29 | `29-auth-project-endpoints.md` | Token auth & project endpoints (create/get/delete) | W5 |
| 30 | `30-template-endpoint.md` | Template PDF endpoint (artifact-cached) | W5 |
| 31 | `31-upload-endpoint.md` | Upload endpoint: validation, quotas, job enqueue | W5 |
| 32 | `32-job-queue-worker.md` | Job queue, worker, lease recovery, handlers | W5 |
| 33 | `33-glyph-endpoints.md` | Glyph endpoints: list, SVG serving, review | W5 |
| 34 | `34-build-artifact-endpoints.md` | Build trigger & artifact download endpoints | W5 |
| 35 | `35-rate-limits-security-headers.md` | Rate limiting & security headers middleware | W5 |
| 36 | `36-retention-deletion.md` | Retention sweeper & deletion flows | W5 |
| 37 | `37-openapi-contract-tests.md` | OpenAPI contract pinning & schemathesis | W5 |
| 38 | `38-security-abuse-suite.md` | Security abuse regression suite (T1–T12) | W5 |
| 39 | `39-webui-scaffold.md` | Web UI scaffold: Vite/React/TS, generated client, i18n, error mapping | W6 |
| 40 | `40-webui-create-open.md` | Web UI: landing, create/open project, token handling | W6 |
| 41 | `41-webui-upload-jobs.md` | Web UI: upload & job progress | W6 |
| 42 | `42-webui-review-grid.md` | Web UI: glyph review grid | W6 |
| 43 | `43-webui-build-preview.md` | Web UI: build, live preview, downloads | W6 |
| 44 | `44-webui-e2e-playwright.md` | Web E2E: Playwright happy/error paths vs compose stack | W6 |
| 45 | `45-docker-compose.md` | Dockerfile (multi-stage) & docker-compose self-host | W7 |
| 46 | `46-flyio-deploy-runbook.md` | Fly.io deploy config & runbook | W7 |
| 47 | `47-pypi-packaging-release.md` | PyPI packaging & release workflow | W7 |
| 48 | `48-user-ops-docs.md` | User & ops docs: README, SECURITY.md, privacy page, printing guide | W7 |
| 49 | `49-v1-acceptance.md` | v1 acceptance run & release checklist | W7 |

## 3. Dependency table

`A ← B` means A depends on B (B must be completed first).

| Issue | Depends on |
|---|---|
| 01 | — |
| 02 | 01 |
| 03 | 01, 02 |
| 04 | 01 |
| 05 | 01, 04 |
| 06 | 01, 04 |
| 07 | 04, 06 |
| 08 | 07 |
| 09 | 07, 08 |
| 10 | 01, 06 |
| 11 | 07, 09, 10 |
| 12 | 09, 11 |
| 13 | 06 |
| 14 | 06, 12, 13 |
| 15 | 05, 06, 10, 11, 12, 13, 14 |
| 16 | 04, 05, 06 |
| 17 | 16 |
| 18 | 04, 16, 17 |
| 19 | 05, 06 |
| 20 | 04, 05, 07, 19 |
| 21 | 07, 08, 19 |
| 22 | 15, 19 |
| 23 | 05, 06, 19 |
| 24 | 16, 17, 18, 19 |
| 25 | 09, 20, 21, 22, 23, 24 |
| 26 | 01, 04, 06, 07 |
| 27 | 26 |
| 28 | 26 |
| 29 | 26, 27, 28 |
| 30 | 07, 08, 28, 29 |
| 31 | 10, 28, 29 |
| 32 | 15, 16, 17, 18, 27, 28, 29, 30 |
| 33 | 06, 29, 32 |
| 34 | 29, 32 |
| 35 | 26, 29 |
| 36 | 27, 28, 29, 32 |
| 37 | 29, 30, 31, 32, 33, 34, 35, 36 |
| 38 | 29, 31, 32, 33, 34, 35, 36 |
| 39 | 37 |
| 40 | 39 |
| 41 | 39, 40 |
| 42 | 39, 40 |
| 43 | 39, 40 |
| 44 | 40, 41, 42, 43, 45 |
| 45 | 32, 35, 39, 40, 41, 42, 43 |
| 46 | 45 |
| 47 | 02, 03, 25 |
| 48 | 25, 45, 46, 47 |
| 49 | all of 01–48 |

## 4. Implementation waves

| Wave | Issues | Theme | Exit criterion |
|---|---|---|---|
| W0 | 01–06 | Repo, CI, domain foundations | CI green; charsets & domain models importable and tested |
| W1 | 07–09 | Template & synthetic corpus | Printable template PDF + sidecar; corpus fixtures generated deterministically |
| W2 | 10–15 | Ingest pipeline | `clean-scan` and `phone-tilt` corpus pages ingest to glyph SVGs with expected coverage |
| W3 | 16–18 | Font build & QA | Golden font builds; fontbakery gate green; proof sheet renders |
| W4 | 19–25 | CLI | Issue 25 golden E2E green — **local product complete** |
| W5 | 26–38 | Hosted service | Contract + abuse suites green — **API product complete** |
| W6 | 39–43, 45, 44 | Web UI + container (45 executes before 44: the E2E suite runs against the compose stack) | Playwright E2E green |
| W7 | 46–49 | Deploy-ready, packaging, docs, acceptance | Issue 49 checklist fully green — **v1 complete** |

Issue numbers are stable identifiers, not a strict execution sequence — the §3 dependency
table is authoritative for ordering. The one deliberate out-of-number-order case: **45
(Docker/compose) executes before 44 (Playwright E2E)** inside W6.

Parallelization notes: within W2, issues 10 and 13 can proceed in parallel after 06/09; within
W5, 27/28 are parallel after 26, and 30/31/33/34/35/36 fan out after 29+32. Issues 04→08 are
the template critical path; 09 unblocks all pipeline testing and should be prioritized.

## 5. Coverage table (DESIGN.md § → issues)

| DESIGN section | Covered by |
|---|---|
| §4 Repository layout | 01 |
| §5 Core domain model | 06 |
| §6 Charsets | 04 |
| §7 Template (geometry, sidecar, PDF) | 07, 08 |
| §8 Ingest stages S1–S8 | 10, 11, 12, 15 |
| §8.3 Re-ingest semantics | 15 (CLI: 22; service: 31/32) |
| §9.1–9.3 Vectorize & fitting | 13, 14 |
| §9.4 Glyph SVG format & parser | 06 |
| §9.5 Warning taxonomy | 12, 14 (surfaced: 18, 23, 33, 42) |
| §9.6 Completer hook | 16 (interface registration only) |
| §10 Font build | 16 |
| §11 QA gate & proof sheet | 17, 18 |
| §12 Local project dir | 05 |
| §13 CLI | 19–25 |
| §14 Service architecture, DB, jobs, retention | 26, 27, 28, 32, 36 |
| §15 HTTP API | 29, 30, 31, 33, 34, 37 |
| §16 Web UI | 39–43 |
| §17 Security model | 03, 06, 10, 28, 29, 31, 35, 36, 38, 45, 48 |
| §18 Testing strategy | 02, 09, 25, 37, 38, 44, 49 |
| §19 Observability | 26 |
| §20 Packaging & deployment | 45, 46, 47 |
| §21 Performance budgets | 25 (CLI), 32 (service), 49 (acceptance) |
| §22 Error registry | 06 (registry), 19 (CLI mapping), 26 (HTTP mapping), 39 (ja strings) |

Every DESIGN v1 behavior is owned by at least one issue; no product behavior lives only in
prose outside this plan.

## 6. Validation strategy (whole product)

1. **Per-issue**: every issue's Validation section is executable by the implementation agent
   (commands + expected results); reviewers rerun them.
2. **Per-wave exit criteria** (§4 table) gate starting the next wave's dependent issues.
3. **Continuous**: CI (02/03) runs unit + golden + property + contract + abuse suites on every
   PR from W0 onward; fixtures from 09 make the pipeline testable without human handwriting.
4. **Product acceptance** (49): scripted run of DESIGN §18.3 — CLI journey on two corpus
   profiles, service journey via Playwright on the compose stack, retention clock test,
   security checklist walk of §17.3 T1–T12, performance budget spot checks (§21).
5. **Real-world validation** (post-v1, human): one real handwritten `ja-basic-v1` font by the
   user on macOS/iOS — deliberately outside agent-verifiable v1 scope; feeds KU-1/KU-3
   calibration.

## 7. Deferred to v2 (from DESIGN §2.3)

D1 digital-ink input adapter (browser canvas) · D2 kanji presets + campaign UX · D3 AI glyph
completion behind `GlyphCompleter` · D4 accounts on top of token projects · D5 OpenType
features (alternates/ligatures) · D6 web glyph editor, local web mode · D7 Postgres + external
queue multi-instance scaling · D8 UI i18n beyond Japanese.

## 8. Known unknowns (may spawn new issues during implementation)

| ID | Unknown | Trigger for new issue |
|---|---|---|
| KU-1 | potrace parameter calibration vs real pens | If golden quality is poor on real samples → "tracing parameter tuning + config exposure" |
| KU-2 | OpenCV 5.x wheel ArUco behavior | If CI smoke test fails on 5.x → "pin/adapt OpenCV version strategy" |
| KU-3 | Phone-photo robustness envelope | If `phone-dark` profile fails rectification → "adaptive marker detection retry ladder" |
| KU-4 | fontbakery universal findings on generated fonts | First golden build → populate allowlist; possibly "metrics adjustments" issue |
| KU-5 | HEIC decode reliability (pillow-heif) across platforms | If flaky → "make HEIC optional extra + UI messaging" |
| KU-6 | PyPI `glyphlab` name squatting before release | If taken at release time → "rename package" decision (ADR) |
| KU-7 | reportlab mm-precision across printers (template scale drift) | If scale ruler feedback shows drift → "printer calibration flow" |
| KU-8 | SQLite WAL behavior on Fly volume snapshots | If corruption observed in staging → "move default to Postgres" (flips ADR-005 default) |

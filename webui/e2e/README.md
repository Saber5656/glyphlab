# Hosted browser acceptance

Run against the real compose stack; no API mocks or synthetic job completions are used.
The browser creates its project and downloads its own template. The Python helper then
reads that project's internal sidecar as the existing Compose app user and stamps two real
scan pages. This read-only export preserves the production artifact mode 0600 across Linux
and Docker Desktop. It verifies that `E2E_DATA_DIR` matches the app's `/data` bind mount;
a missing stack, incorrect bind, or failed read is an error.
Generating the corpus after UI creation avoids a second setup-only project and also proves
that the uploaded scans match the newly printed template.

From the repository root, after installing the locked Python and Node dependencies:

```bash
install -d -m 0777 e2e-data
docker compose -f deploy/docker-compose.yml -f deploy/compose.e2e.yml up -d --build --wait
cd webui
npx playwright install --with-deps chromium webkit
E2E_PYTHON=../.venv/bin/python npx playwright test
```

Environment variables:

| Name                | Default                  | Purpose                                                       |
| ------------------- | ------------------------ | ------------------------------------------------------------- |
| `E2E_BASE_URL`      | `http://localhost:8080`  | Real service origin, optionally Vite proxy for debugging      |
| `E2E_API_URL`       | `E2E_BASE_URL`           | Health endpoint origin when the UI uses a separate Vite proxy |
| `E2E_DATA_DIR`      | `../e2e-data` from webui | Bind mount containing the service's `store/projects`          |
| `E2E_COMPOSE_PROJECT` | Compose default / `COMPOSE_PROJECT_NAME` | Explicit project name for an isolated acceptance stack |
| `E2E_PYTHON`        | `../.venv/bin/python`    | Python with the repository core/test dependencies             |
| `E2E_FAILURE_PROBE` | unset                    | Select only the deliberately failing artifact diagnostic      |

Two serial tests share one project per browser: the main journey and upload errors plus
deletion. The matrix uses Chromium, WebKit, and Pixel 7 Chromium in Japanese. One worker
keeps the worker/CPU budget bounded; the normal matrix creates only three projects. A CI
retry repeats the serial group, for at most six project creations. The create flow honors a
short `Retry-After`; a daily quota failure remains a failure requiring a fresh, authorized
stack or its natural reset. Rate limits are never overridden. Do not repeatedly rerun against
an existing shared stack after consuming its daily allowance.

The tests verify PDF magic, two processed scans, persisted review counts, a loaded custom
FontFace (in addition to `document.fonts.check`), artifact SHA-256 against the listing observed
from the UI, a fresh browser context's fragment consumption, no token in request URLs,
blank-image marker guidance and retry, client-only oversize rejection, deletion, and expiry.
All state changes use the public UI. The only internal read is the template sidecar.

Failure diagnostics are retained in `test-results/` and `playwright-report/`. Verify retention
without spending any project quota:

```bash
E2E_FAILURE_PROBE=1 npx playwright test --project=chromium
```

This command must fail deliberately and produce `trace.zip`, `video.webm`, and a screenshot.
The introducing local run verified all three. CI should upload these diagnostic directories
with `if: failure()` (or `always()` for the intentional probe); the CI run is the evidence
that uploading succeeded. The probe is excluded from normal acceptance.

Project teardown uses the Delete UI even after a failed journey. Failure traces can contain
the ephemeral test token; keep diagnostics private until deletion has revoked that token.
Never publish artifacts for a project whose cleanup failed. No browser-level sleeps are used;
waits observe downloads, responses, DOM state, font state, or a server-provided retry deadline.

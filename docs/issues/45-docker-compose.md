# Title

Dockerfile (multi-stage) & docker-compose self-host stack

# Summary

Build the hardened production image per DESIGN §17.5/§20 — webui build stage, Python
runtime stage with potrace, non-root, read-only rootfs — plus the one-command self-host
`docker-compose.yml`.

# Context

The image is both the self-host product (persona P3) and the Fly.io deploy unit (46); the
E2E suite (44) runs against it, so it must exist before W6 completes.

# Scope

`deploy/{Dockerfile,docker-compose.yml,compose.e2e.yml}` + repo-root `.dockerignore` (the
build context is the repo root, so the root file is the one Docker reads) + a `ci.yml`
`image` job building the image and running the smoke test.

# Detailed Requirements

1. `Dockerfile` (multi-stage):
   - Stage `webui`: `node:20-slim` (digest-pinned) → `npm ci && npm run build` in
     `/webui`.
   - Stage `runtime`: `python:3.12-slim-bookworm` (digest-pinned) →
     `apt-get install -y --no-install-recommends potrace && rm -rf /var/lib/apt/lists/*`;
     install uv (pinned); `uv sync --locked --no-dev --package glyphlab-service`; copy
     workspace source; copy webui dist to `/app/webui-dist` (served by the app per §14.1);
     create user `app` (uid 10001); `USER app`; `ENV GLYPHLAB_DATA_DIR=/data
     GLYPHLAB_WEBUI_DIST=/app/webui-dist GLYPHLAB_ENVIRONMENT=prod` (settings fields from
     issue 26 / DESIGN §20); `EXPOSE 8080`; exec-form healthcheck `HEALTHCHECK CMD
     ["python", "-c", "import urllib.request;
     urllib.request.urlopen('http://127.0.0.1:8080/healthz')"]`; entrypoint = a **Python
     module, not a shell script** (§17.5 no-runtime-shell): `ENTRYPOINT ["python", "-m",
     "glyphlab_service.entry"]` which runs the migrate step programmatically (issue 27's
     alembic API) then starts uvicorn (host 0.0.0.0, port 8080, workers 1 per §14.1).
2. Image budget: < 900 MiB uncompressed (opencv+scipy-free — verify no scipy sneaks in);
   report size in CI log.
3. `docker-compose.yml` (self-host): one service, `volumes: [glyphlab-data:/data]`,
   `read_only: true` + `tmpfs: [/tmp]`, `cap_drop: [ALL]`, `security_opt:
   [no-new-privileges:true]`, port 8080, restart unless-stopped, env passthrough with sane
   defaults. Optional commented Postgres block (documented, off by default per ADR-005).
4. `compose.e2e.yml` override per issue 44 (bind mount `./e2e-data:/data`, short
   retention env + `GLYPHLAB_SWEEP_INTERVAL_S=5`, fixed `SOURCE_DATE_EPOCH`).
5. `.dockerignore`: everything not needed (docs, tests, .git, webui/node_modules).
6. CI job `image` in `.github/workflows/ci.yml` (same triggers/permissions as the other
   jobs: `contents: read`): `docker/setup-buildx-action` + `docker/build-push-action`
   (both SHA-pinned) with `cache-from/to: type=gha`, `push: false`, `tags: glyphlab:ci`,
   then the compose smoke of the Validation block. Trivy scan deferred (post-v1
   candidate; pip-audit covers Python deps).
7. Rootfs read-only compliance: app writes only to `/data` and `/tmp` — any violation
   surfaces in the smoke test (document the invariant in Dockerfile comments).

# Acceptance Criteria

- [ ] `docker compose -f deploy/docker-compose.yml up -d --build` from a clean checkout
      reaches healthy and serves the SPA at `/` (this is the documented self-host
      command; README/48 uses the same `-f` form).
- [ ] Validation block passes in full (uid, ro-rootfs, caps, potrace, smoke, size,
      digest pins).

# Validation

```bash
docker compose -f deploy/docker-compose.yml up -d --build
for i in $(seq 1 30); do curl -sf localhost:8080/healthz && break; sleep 1; done
curl -s localhost:8080/ | head -3
# container hardening assertions:
CID=$(docker compose -f deploy/docker-compose.yml ps -q)
docker inspect "$CID" --format '{{.Config.User}}' | grep -q 10001
docker inspect "$CID" --format '{{.HostConfig.ReadonlyRootfs}}' | grep -q true
docker inspect "$CID" --format '{{.HostConfig.CapDrop}}' | grep -qi all
docker compose -f deploy/docker-compose.yml exec app potrace --version | head -1
# functional smoke: create project + template magic bytes
TOK_JSON=$(curl -sf -X POST localhost:8080/api/projects -H 'content-type: application/json'   -d '{"name":"smoke","family_name":"Smoke","charset_id":"ascii"}')
PID=$(echo "$TOK_JSON" | python3 -c "import sys,json;print(json.load(sys.stdin)['project_id'])")
TOK=$(echo "$TOK_JSON" | python3 -c "import sys,json;print(json.load(sys.stdin)['token'])")
curl -sf "localhost:8080/api/projects/$PID/template.pdf" -H "Authorization: Bearer $TOK" | head -c4 | grep -q %PDF
# hygiene: pinned bases + size budget
grep -E "FROM .+@sha256:" deploy/Dockerfile | wc -l | grep -q 2
docker image inspect glyphlab:ci --format '{{.Size}}' | awk '{exit !($1 < 900*1024*1024)}'
docker compose -f deploy/docker-compose.yml down -v
```

# Dependencies

32, 35, 39–43 (webui dist), effectively W5 complete.

# Non-goals

Fly.io specifics (46), registry publishing (post-v1 release decision), multi-arch builds
(amd64 only in v1; arm64 noted as fast-follow).

# Design References

DESIGN §20 (Docker, env names incl. WEBUI_DIST/ENVIRONMENT), §17.5 (container
hardening, no runtime shell), §14.1 (single process), ADR-005.

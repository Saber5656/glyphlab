# Title

Web UI scaffold: Vite + React + TS, generated API client, i18n table, error mapping

# Summary

Bootstrap `webui/`: Vite React TypeScript SPA, typed API client generated from the committed
`openapi.json`, the Japanese string table with typed keys, §22 error-code → ja message
mapping, routing shell, and webui CI job.

# Context

All four UI feature issues (40–43) build on these conventions. The client-generation step is
what makes the OpenAPI pin (37) pay off.

# Scope

`webui/` scaffold + `.github/workflows/ci.yml` extension (webui job). No feature pages
beyond a shell.

# Detailed Requirements

1. Scaffold: Vite 6+, React 18+, TypeScript strict, ESLint (typescript-eslint) + Prettier;
   `npm ci`-reproducible lockfile; Node ≥ 20. No UI framework beyond hand-rolled CSS
   (single `app.css`, CSS custom properties, mobile-first — the audience often arrives on
   phones); no CSS-in-JS, no external fonts/CDN, no analytics/trackers (§16.4).
2. API client: `openapi-typescript` (types emitted to `webui/src/generated/api.d.ts`) +
   a thin hand-written wrapper `webui/src/lib/api.ts`:
   `apiFetch(path, {method?, body?, projectId?, raw?}) -> Promise<T | Blob>` — base
   `/api`; when `projectId` is given, injects `Authorization: Bearer <token from
   token.ts>`; non-2xx parses the envelope into a thrown typed
   `ApiError {code, message, detail, status}`; `raw: true` returns a Blob (template/
   artifact/SVG downloads). Generation: `npm run gen:api` reads
   `../packages/service/openapi.json`; committed output, drift-checked in CI via
   `npm run gen:api && git diff --exit-code src/generated/` (same pattern as 37).
3. Token storage module `src/lib/token.ts`: `saveToken(projectId, token)` /
   `getToken(projectId)` over `localStorage` (key `glyphlab:token:<id>`); fragment
   handling per §16.2: on route load, `#t=glp_...` → save → `history.replaceState` strip;
   unit-tested with jsdom.
4. i18n: `src/i18n/ja.ts` — `export const ja = {...} as const satisfies Record<MsgKey,
   string>`; typed `t(key, params?)`; includes the error map with **exactly the DESIGN
   §16.3 canonical table strings** (all §22 codes + the §9.5 warning chip labels;
   fallback 「エラーが発生しました（{code}）」). A unit test iterates
   `src/generated/error-codes.json` (exported by issue 37's script, committed) and
   asserts every code has a ja entry.
5. Routing (react-router): `/` (placeholder landing), `/p/:projectId` layout route with
   token guard (missing token → prompt screen asking for token paste — reused by 40),
   nested `upload | review | build` placeholders.
6. React Query (TanStack) configured: default retry 1, `refetchOnWindowFocus` false; job
   polling helper `usePollJob(projectId, jobId)` (1 Hz per §15; stops on the §14.3
   terminal states: succeeded / failed / canceled).
7. CI job `webui`: `npm ci && npm run lint && npm run typecheck && npm run test && npm run
   build`; build artifacts NOT committed (Docker builds them in 45); api-types drift check.
8. Vitest + Testing Library set up with one real test per module above (token fragment,
   t() fallback, apiFetch error envelope parsing).

# Acceptance Criteria

- [ ] `npm run build` succeeds and `npm run preview` serves the shell (Validation).
- [ ] Fragment token flow proven by jsdom test (URL cleaned, storage populated).
- [ ] Every code in `error-codes.json` has a `ja.ts` entry (unit test).
- [ ] webui CI job present in `.github/workflows/ci.yml` incl. the gen:api drift check
      (grep in Validation).

# Validation

```bash
cd webui && npm ci && npm run gen:api && git diff --exit-code src/generated/
npm run lint && npm run typecheck && npm test && npm run build
(npm run preview -- --port 4173 &) && sleep 2 && curl -sf http://localhost:4173/ | head -3 && kill %1 2>/dev/null || true
grep -n "gen:api" ../.github/workflows/ci.yml
```

# Dependencies

37.

# Non-goals

Feature pages (40–43), E2E (44), visual design polish beyond a clean baseline, i18n
languages other than ja (D8).

# Design References

DESIGN §16 (routes, token, strings, guardrails), §15 (client contract), §22 (codes).

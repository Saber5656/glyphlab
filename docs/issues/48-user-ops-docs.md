# Title

User & ops documentation: README, SECURITY.md, privacy page, printing guide

# Summary

Write the outward-facing documentation set: a bilingual-lead README (ja primary, en
summary), CLI quickstart, self-host guide, SECURITY.md with a vulnerability-report channel,
the web privacy page content, and the physical printing/writing guide that ingest quality
depends on.

# Context

Docs are part of the product surface (persona P3 depends on them entirely) and part of the
security posture (§17.7 promises must be stated where users can read them).

# Scope

`README.md` (rewrite), `SECURITY.md`, `CONTRIBUTING.md` (light), `docs/guide/{cli.md,
self-host.md,printing.md}`, `scripts/run_readme_quickstart.sh` (executes the README CLI
block), and the privacy page: `webui/src/pages/Privacy.tsx` **with all strings in
`webui/src/i18n/ja.ts`** (§16.5 — components never hold literals), route `/privacy`
added and linked from the landing page footer (the footer is introduced here; §16.1
lists routes only).

# Detailed Requirements

1. `README.md` (ja primary, short English intro at top):
   - The pitch + 3-step visual description; badges (CI, license); feature table vs scope
     (何ができる/できない — honest NG list from §2.2).
   - Quickstart (hosted): 4 steps with the public URL placeholder.
   - Quickstart (CLI): install (`pip install glyphlab` + `brew install potrace` note /
     `pip install 'glyphlab[trace]'` fallback), then the §13 command journey with real
     command output samples. `scripts/run_readme_quickstart.sh` executes exactly the
     README's fenced commands in a temp venv — substituting `pip install glyphlab` with
     `pip install dist/glyphlab-*.whl` (built via issue 47's `uv build`) until the first
     real PyPI release exists; the substitution rule is stated in a README comment.
   - Self-host: `docker compose up` one-liner + link to guide.
   - License section: code MIT; **fonts you generate are yours** (explicit, §10.4);
     potrace GPL-2 subprocess note (ADR-004 wording).
2. `docs/guide/printing.md` (ja): paper (A4普通紙/コピー用紙), print at 100% (equal-scale)
   with the ruler check, pen guidance (太さ0.5–1.0mm、黒/濃紺、鉛筆・シャープペン非推奨),
   writing tips (ガイドに合わせる、枠に触れない、失敗したら塗りつぶさず新しい用紙),
   photo tips (§16.3 error remediations consolidated: 明るい場所、真上から、ページ全体、
   影を避ける), FAQ (かすれた字/はみ出し/書き直し).
3. `docs/guide/cli.md`: full command reference generated-then-curated from §13 (exit
   codes, JSON mode, custom charset TOML example per §12.2 schema and §17.4 limits);
   `docs/guide/self-host.md`: compose bring-up (`docker compose -f
   deploy/docker-compose.yml up`, matching issue 45), env table (every `GLYPHLAB_*` from
   settings with default+meaning — drift check hooks into 46's `check_runbook.sh`),
   backup, upgrade.
4. `SECURITY.md`: supported versions (latest minor), report via GitHub private security
   advisories (no email in v1), 90-day coordinated disclosure default, scope notes (hosted
   instance abuse reports welcome), link to threat model section in DESIGN.
5. Privacy page (ja, static strings in webui): what is stored (手書き画像は処理後すぐ削除、
   抽出データとフォントは最終アクセスから14日で自動削除), no accounts/no analytics/no
   third-party requests, IP in abuse logs ≤ 7日, delete-now instructions, self-host
   pointer. Content mirrors §17.7 exactly — a docs/privacy drift is a bug.
6. `CONTRIBUTING.md`: dev setup (uv, npm, potrace), test commands per package, PR
   expectations (CI green, no direct pushes to main), link to ISSUE_PLAN for roadmap.
7. All claims must match implemented behavior (retention days, limits) by referencing
   settings defaults — a doc test greps documented numbers against `settings.py` defaults
   (simple regex assertions, same spirit as 46's drift guard).

# Acceptance Criteria

- [ ] `scripts/run_readme_quickstart.sh` green locally and as a CI step (added to
      ci.yml).
- [ ] Privacy/security docs consistent with §17.7 and settings defaults (drift test
      green).
- [ ] Validation's route/link/placeholder greps all pass.

# Validation

```bash
uv build --package glyphlab && bash scripts/run_readme_quickstart.sh
uv run pytest packages/service/tests/test_doc_drift.py -q
grep -q 'path="/privacy"' webui/src/App.tsx            # route registered
grep -rq 'to="/privacy"' webui/src/pages/Landing.tsx   # footer link
grep -q "security/advisories/new" SECURITY.md          # advisory channel documented
! grep -rn "TODO\|TBD" README.md SECURITY.md docs/guide/ | grep -v "post-v1"
```

# Dependencies

25, 45, 46, 47 (wheel build for the quickstart runner).

# Non-goals

Docs site generator (plain Markdown in v1), English full docs (D8), marketing site.

# Design References

DESIGN §17.7, §16.1 (routes; footer added here), §16.5 (strings in ja.ts), §13, §12.2/
§17.4 (charset example), §20; ADR-002 (privacy promises), ADR-004 (license note).

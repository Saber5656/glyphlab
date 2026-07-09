# Title

Web UI: build trigger, live font preview, downloads

# Summary

Implement `/p/:id/build` per DESIGN §16.1: trigger builds, poll the build job, render a live
`@font-face` preview with an editable sample, and offer artifact downloads (TTF/WOFF2/proof/
QA report) — the payoff screen.

# Context

The preview is the moment users see their handwriting typed back at them; it must load the
freshly built WOFF2 via authenticated fetch and apply it safely.

# Scope

`webui/src/pages/Build.tsx` + font-loading hook + tests.

# Detailed Requirements

1. Build trigger: 「フォントを生成」 button → `create_build`; disabled while a build job
   is queued/running (poll via `usePollJob`); `E_BUILD_IN_PROGRESS` (409 on race) surfaces
   as info and resumes polling `error.detail.job_id` (canonical per issue 34's contract).
   Nothing-to-build 422 (`detail.reason == "nothing_to_build"`) → ja guidance linking to
   review.
2. QA outcome: success → artifacts section; `E_QA_FAILED` → warning panel (「生成された
   フォントは品質チェックに失敗しました」) with failing check ids + QA report download still
   offered (artifacts exist per §10.1/32) and 「問題を確認して作り直す」 guidance.
3. Live preview:
   - Hook `useProjectFont(projectId)`: find latest woff2 artifact → authenticated blob
     fetch → `new FontFace("GlyphlabPreview", buffer)` → `document.fonts.add`; cleanup
     deletes the FontFace on unmount/rebuild (no accumulation).
   - Editable `<textarea>` — default text is exactly issue 18's `MIXED` sample string
     (きょうは「Glyphlab」でフォントを作った。…, duplicated as a ja.ts constant) —
     rendered in the loaded font at 3 sizes; missing-glyph note: fetch `list_glyphs` once
     (react-query, shared with 42's cache) and compute the set of chars whose status is
     missing/rejected or outside the charset; typed characters in that set are listed
     under the preview (「この文字はフォントに含まれません: …」).
4. Downloads: buttons for ttf / woff2 / proof.html / qa-report.json via authenticated blob
   + `download` attribute object URL; file names from Content-Disposition when present.
   「インストール方法」 collapsible (macOS/iOS/Windows short ja instructions — static
   strings).
5. History: group the artifact listing by `job_id` (§15/§14.2 — each build's
   ttf/woff2/proof/qa share it), newest group first (≤ 3 groups per 34's pruning), with
   timestamps; selecting an older group previews its woff2.
6. Tests (msw): trigger→poll→artifacts flow; 409-with-`detail.job_id` resume; QA-failed
   rendering; FontFace lifecycle (jsdom stub) added/removed; missing-glyph detection for
   typed text (statuses from mocked `list_glyphs`); job_id grouping renders 2 mocked
   builds as 2 groups; download uses blob fetch (no `<a href="/api/...">` bare links —
   assert none in DOM).

# Acceptance Criteria

- [ ] Full build→preview→download happy path tested; FontFace cleanup proven.
- [ ] QA-fail path shows artifacts + guidance (not a dead end).
- [ ] No unauthenticated URL ever placed in DOM attributes (test scans rendered DOM).
- [ ] Build-history grouping by job_id covered by test.

# Validation

```bash
cd webui && npm run typecheck && npm test -- --run src/pages/__tests__/build.test.tsx
```

# Dependencies

39, 40. (Issue 34's endpoints — incl. the 409 `detail.job_id` contract — are available
because W5 precedes W6.)

# Non-goals

Font subsetting options, sharing links (v2), proof-sheet inline iframe (download/open only —
keeps CSP posture simple).

# Design References

DESIGN §16.1 (build route), §15 (builds/artifacts incl. job_id), §11.3 (sample text
categories; exact string from issue 18), issue 32 (QA-fail artifact persistence).

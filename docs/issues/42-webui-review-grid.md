# Title

Web UI: glyph review grid

# Summary

Implement `/p/:id/review` per DESIGN §16.1: the charset-ordered glyph grid with SVG
previews, status filters, explicit accept/reject actions (single and bulk), and keyboard
navigation.

# Context

Review is the human quality gate before build (§8.3 gives ACCEPTED glyphs overwrite
protection). The grid must stay usable for 276 cells on a phone.

# Scope

`webui/src/pages/Review.tsx` + grid/cell components + tests.

# Detailed Requirements

1. Data: `list_glyphs` (single page, limit 300 covers v1 presets); client groups into
   sections 英数 / ひらがな / カタカナ / 記号 by deriving the script class locally from
   codepoint ranges (§6.1 assignment rules: U+0020–007E → 英数, U+3041–3096 → ひらがな,
   U+30A1–30FA + U+30FC → カタカナ, rest of the kana-preset punct → 記号) in charset
   order — no API change needed.
2. Cell rendering: `<img src={svg_url}>` is impossible (Authorization header) → fetch
   SVG via `apiFetch` blob → object URL rendered ONLY through `<img src={blobUrl}>`
   (never inline SVG injection / `dangerouslySetInnerHTML` — §17.3 T7), cached per
   `codepoint+updated_at` (both from the issue-33 list response) in a small LRU (≤ 350
   entries, revoked on eviction); `missing` → dashed placeholder with the target char in
   system font (light gray); status border colors per issue 18's scheme (auto=blue,
   accepted=green, rejected=red strikethrough, missing=gray); warning badge dot with the
   §16.3 ja chip label as tooltip.
3. Interactions:
   - Tap/click cycles nothing implicitly — explicit buttons on a focused cell: 採用 /
     却下 (calls `review_glyphs` single-item; optimistic update, rollback on error).
   - Multi-select mode (long-press / checkbox toggle) → bulk 採用/却下 (batched ≤ 400).
   - Header actions: 「AUTOをすべて採用」 (confirm dialog with count), filter chips
     (すべて / 未確認(auto) / 採用 / 却下 / 未取込(missing) / 警告あり), text search by
     char/codepoint.
   - Keyboard: arrows move focus, `a` accept, `r` reject, `Esc` clears selection (§16.4).
4. Status footer: counts per status + 「ビルドへ」 CTA enabled when accepted+auto > 0.
5. Perf: virtualization NOT needed at 276 drawn cells (measure first — plain grid with
   `content-visibility: auto`); document the D2 (kanji) note that v2 will need
   virtualization + pagination.
6. Tests (msw): grid renders per fixture statuses incl. section grouping; optimistic
   accept with server error rollback; multi-select mode → bulk 採用/却下 issues one
   batched call (selection cleared after); 「AUTOをすべて採用」 confirm flow; filters/
   search narrow correctly; keyboard a/r on focused cell; blob URL cache eviction (no
   leak: revoke spy); no `dangerouslySetInnerHTML` anywhere in the page (source-grep
   test).

# Acceptance Criteria

- [ ] All interactions covered by tests; zero unhandled-rejection warnings in test run.
- [ ] Missing/rejected/auto/accepted visual states distinct and labeled (aria-label with
      status for a11y).
- [ ] Review round-trip reflected in project summary (msw handlers share state).
- [ ] Object-URL lifecycle leak-free per test.

# Validation

```bash
cd webui && npm test -- --run src/pages/__tests__/review.test.tsx
```

# Dependencies

39, 40. (The issue-33 endpoints are available because wave W5 precedes W6 — ISSUE_PLAN §4.)

# Non-goals

Glyph editing (NG6), re-mapping cells to other codepoints, virtualized rendering (v2 D2).

# Design References

DESIGN §16.1 (review route), §16.4 (keyboard/a11y), §16.3 (chip labels), §9.5
(warnings), §6.1 (script-class ranges), §5 (statuses), §15 (glyph endpoints), §17.3 T7.

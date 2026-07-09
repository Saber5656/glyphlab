# Title

Web UI: landing, create/open project, token handling, project home

# Summary

Implement the entry experience per DESIGN §16.1–§16.2: landing page (product explanation +
create form + open-existing), the show-once token panel, and the project home checklist with
coverage stats.

# Context

The token UX is the security-critical moment of the whole web product (ADR-002): users must
save an unrecoverable secret without an account system to fall back on.

# Scope

`webui/src/pages/{Landing,ProjectHome}.tsx` + create/open components + tests.

# Detailed Requirements

1. Landing `/`:
   - Explanation section (ja): 3-step visual (印刷して書く → 撮って送る → フォントを受け取る) +
     privacy note (アカウント不要・最終アクセスから{retention_days}日で自動削除 —
     `retention_days` comes from `GET /api/meta`, §15/issue 26 contract).
   - Create form with client-side mirrors of the server rules (server remains authority):
     name 1–64 chars after NFC, no control chars, no leading/trailing whitespace (§17.4);
     family name per §10.4 constraint `^[A-Za-z0-9][A-Za-z0-9 \-]{0,30}$`, live-validated
     with a ja explanation of why ASCII; charset select from `/api/meta` (shows
     文字数と枚数). Submit → `create_project`.
   - Open-existing: paste a full URL `/p/<uuid>#t=glp_...` or separate id + token fields;
     parsing: uuid via RFC-4122 pattern, token via `^glp_[A-Za-z0-9_\-]{43}$`; anything
     else → inline ja error. Parse & save → navigate.
2. Token panel (post-create modal, cannot be dismissed for 5 s): shows the shareable link
   `origin/p/<id>#t=<token>` in a copy field + 「このリンクを失うとプロジェクトは開けません。
   ブックマークかメモに保存してください」; explicit copy button with copied-state; also
   auto-saved to localStorage note. Token never rendered again after dismissal (§16.2).
3. Project home `/p/:id`:
   - Fetch summary (react-query); 404 → token-prompt screen (invalid/expired message,
     §16.3 strings).
   - Checklist: ① テンプレートを印刷 (download button → template.pdf via `apiFetch`
     blob + object URL, never a bare `<a href>` — Authorization is a header) ②
     書いてアップロード (→ upload) ③ 確認 (→ review) ④ フォント生成 (→ build). Step
     states derive ONLY from the §15 summary counts (②のdone ⇔ non-missing > 0; ③のdone ⇔
     accepted > 0; ①は完了検知不能のため常にアクション表示 — template-download completion
     is not knowable server-side and is not tracked).
   - Expiry banner: 残り日数 + 今すぐ削除 button (confirm dialog, calls DELETE, clears
     localStorage, navigates home with a "deleted" toast).
4. Tests: create flow (msw-mocked API) → token panel → localStorage populated → navigation;
   open-existing parsing (URL form + id/token form + garbage rejection); 404 → prompt
   screen; delete flow clears storage.

# Acceptance Criteria

- [ ] Full create→home happy path in jsdom tests with msw.
- [ ] Token shown exactly once; navigating back to home never re-renders it.
- [ ] Template downloads via authenticated fetch (no token in any URL except the fragment
      link display).
- [ ] All strings from `ja.ts` — enforced by a **unit test** (runs under `npm test`, so
      Validation covers it) that greps `src/pages/**/*.tsx` for kana/kanji literals
      outside `i18n/`.

# Validation

```bash
cd webui && npm test -- --run src/pages/__tests__/landing.test.tsx src/pages/__tests__/home.test.tsx
```

# Dependencies

39. (`retention_days` in `/api/meta` is already part of issues 26/37's canonical
contract — no service change belongs to this issue.)

# Non-goals

Upload/review/build pages (41–43), account recovery (none exists by design).

# Design References

DESIGN §16.1–§16.3, §15 (create/meta/template endpoints), ADR-002 (token UX rationale).

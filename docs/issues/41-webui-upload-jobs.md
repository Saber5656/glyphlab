# Title

Web UI: upload page & job progress

# Summary

Implement `/p/:id/upload` per DESIGN §16.1: drag-drop/file-picker upload (≤ 6 files
queued), per-file ingest-job polling, and per-page result display with actionable Japanese
error messages.

# Context

This page absorbs the messiest real-world input (phone photos); its error rendering is the
UX face of the §22 error codes (`E_PAGE_BLURRY` → retake guidance).

# Scope

`webui/src/pages/Upload.tsx` + upload queue hook + tests.

# Detailed Requirements

1. Input: drag-drop zone + `<input type=file multiple accept="image/jpeg,image/png,
   image/heic">`; client-side prechecks mirroring issue 10's server rules (size ≤ 12 MiB;
   magic bytes of the first 32 bytes read via `File.slice` — JPEG `FF D8 FF` / PNG 8-byte
   signature / HEIC `ftyp`+brand; the 36 MP pixel cap stays server-side) with instant ja
   feedback — server remains the authority.
2. Upload queue hook `useUploadQueue(projectId)`: sequential upload (one at a time — the
   server has per-project queue caps and worker concurrency 1 per §14.1; parallel gives
   no speedup), per-item states `waiting → uploading (progress % via `XMLHttpRequest`
   `upload.onprogress` — this single call site uses XHR because `fetch` cannot report
   upload progress; errors still normalized into issue 39's `ApiError` shape) →
   processing (job poll via usePollJob) → done | error`; `deduplicated: true` responses
   (§15 200 variant) render as 「アップロード済みのページです」 info state.
3. Result rendering per file (job `result` carries issue 15's `PageIngestResult`:
   `counts.extracted/empty/skipped_accepted/failed` + `cells[]`):
   - Success: page number (`page_index + 1`), counts (抽出 N / 空欄 N / スキップ N /
     失敗 N), warning chips aggregated over `cells[].warnings` using the §16.3 canonical
     chip labels, link 「確認画面へ」.
   - Page-level error: the §16.3 canonical ja message for `error_code` + collapsible
     technical code; retry button (re-enqueues the file).
4. Coverage strip at top: overall drawn-glyph coverage bar (from project summary refetch on
   each completion) + 「すべてのページを取り込むと〇〇字」.
5. Concurrency/cancel: leaving the page keeps completed state (react-query cache) but
   cancels pending polls; a `beforeunload` warning while uploads are in flight.
6. Tests (msw): queue state machine transitions incl. job failure; limit errors surfaced
   with the right §16.3 strings — 429 `E_RATE_LIMITED` and 409 `E_QUOTA_EXCEEDED` as
   distinct cases; dedup path; client precheck rejects a 13 MiB blob and a zip-magic file
   without network calls; retry re-posts; XHR progress events drive the % state (mocked
   XHR).

# Acceptance Criteria

- [ ] Full queue lifecycle covered by tests; no orphaned polls after unmount (fake-timer
      leak assertion).
- [ ] Every ingest-related §22 code renders its §16.3 string (parametrized test over the
      map).
- [ ] Sequential upload verified (msw records ordering).
- [ ] Coverage strip updates after each processed page.

# Validation

```bash
cd webui && npm test -- --run src/pages/__tests__/upload.test.tsx
```

# Dependencies

39, 40.

# Non-goals

Camera capture UI (file picker covers phones natively), chunked/resumable uploads, review
actions (42).

# Design References

DESIGN §16.1 (upload route), §16.3 (error strings), §15 (upload/job endpoints), §17.6
(limits the UI must surface gracefully).

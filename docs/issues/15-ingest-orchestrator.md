# Title

Ingest orchestrator: compose S1–S8 + vectorize/fit, report, re-ingest semantics

# Summary

Compose decode → rectify → cells (§8.2 S1–S8) → trace → fit (§9.1–§9.3) into
`ingest_scan()`, persist glyph SVGs and statuses through a storage-agnostic sink, honor
DESIGN §8.3 re-ingest rules, and emit the machine-readable ingest report.

# Context

This is the core library's public "process a scan" API — the single function the CLI (22) and
the service worker (32) both call. Charset/template mismatch protection (§6.2) lives here.

# Scope

`packages/core/src/glyphlab/ingest/{orchestrator.py,sinks.py,report.schema.json}` + tests.
`sinks.py` contains the `GlyphSink` protocol AND `ProjectGlyphSink`, the adapter over issue
05's `ProjectStore` (status.json + glyph SVG writes) used by the CLI (issue 22 imports it;
the service implements its own sink in issue 32). Everything below is composition; no new
algorithmic logic.

# Detailed Requirements

1. `ingest_scan(data: bytes, *, sidecar: TemplateSidecar, charset: CharsetSpec, store:
   GlyphSink, engine: VectorizerEngine, force: bool = False) -> PageIngestResult`.
   - `GlyphSink` protocol (in `sinks.py`): `get_status(cp) -> GlyphStatus` and
     `put_glyph(Glyph, svg_bytes)`. Implementations: `ProjectGlyphSink` (here, over issue
     05's `ProjectStore`) and the service sink (issue 32). The orchestrator stays
     storage-agnostic; skip decisions are recorded in the report, not in the sink.
2. Guard: the sidecar's `charset_id` and `charset_version` fields must equal the project
   charset (§6.2) → `E_TEMPLATE_MISMATCH` (pass `expected_charset` to issue 07's
   `read_sidecar`).
3. Flow: S1 decode (10) → S2–S4 rectify (11) → S5–S8 cells (12) → per-OK-cell:
   **re-ingest gate first** (consult `sink.get_status`; an `ACCEPTED` glyph with
   `force=False` is skipped before any trace/fit work — protection must not depend on
   trace success) → trace (13) → fit (14) → SVG bytes (06 writer) → `sink.put_glyph`.
4. Re-ingest gate (§8.3): target glyph status `ACCEPTED` and `force=False` → cell outcome
   `skipped_accepted`; `MISSING/AUTO/REJECTED` → overwrite with fresh `AUTO`. Empty cells
   never delete existing glyphs (a blank cell on a re-scan is not an erasure command);
   their outcome is `empty`.
5. `PageIngestResult` (JSON-serializable), single source of truth for outcomes — no
   separate arrays: `{"schema": "glyphlab.ingest-report/1", "page_index": int,
   "template_id": str, "counts": {"extracted": int, "empty": int, "skipped_accepted": int,
   "failed": int}, "cells": [{"codepoint": "U+XXXX", "outcome":
   "extracted|empty|skipped_accepted|failed", "warnings": [...], "error_code": str?}],
   "diagnostics": {...}}` — machine schema checked in as
   `packages/core/src/glyphlab/ingest/report.schema.json`; `counts` must equal the cell
   outcome tallies (validated).
6. Page-level failures (S1–S4) raise; the caller maps them (CLI exit 3 / job `failed` with
   `error_code`). Cell-level trace failures (`E_TRACE_TIMEOUT` on one cell) mark that cell
   `failed` and continue — one bad cell must not kill a page.
7. Deterministic ordering: cells processed in sidecar order; report arrays sorted by
   codepoint.
8. Integration tests on corpus: full `clean-scan` page 0 (49 cells) → 48 extracted + 1
   seeded-empty per the corpus manifest; re-run after accepting one glyph → that glyph in
   `skipped_accepted`; `force=True` overwrites it.

# Acceptance Criteria

- [ ] Corpus integration matches manifests exactly on `clean-scan` and `phone-tilt`.
- [ ] Accepted-glyph protection + `force` behavior proven by tests, including: gate fires
      BEFORE trace (a monkeypatched always-failing tracer still yields `skipped_accepted`
      for accepted cells).
- [ ] Charset/template mismatch raises `E_TEMPLATE_MISMATCH` (test with a foreign
      sidecar).
- [ ] One cell's injected trace timeout yields `failed` for that cell, page still succeeds.
- [ ] Report validates against a checked-in JSON Schema
      (`packages/core/src/glyphlab/ingest/report.schema.json`).

# Validation

```bash
uv run pytest packages/core/tests/ingest/test_orchestrator.py -q
```

# Dependencies

05, 06, 10, 11, 12, 13, 14.

# Non-goals

CLI UX (22), job/queue mechanics (32), parallelism (worker's concern), digital-ink adapter
(v2 D1 — but keep the §8.1 `GlyphSource` seam respected: cells flow through an iterator).

# Design References

DESIGN §8 (stages, §8.3 re-ingest), §6.2 (mismatch guard), §22 (codes), §5 (statuses).

# Title

CLI command: `ingest`

# Summary

Implement `glyphlab ingest [FILES...]`: run the issue-15 orchestrator over scan files, persist
glyphs into the project, write the ingest report under `work/`, and print an actionable
per-page/per-cell summary — per DESIGN §13.

# Context

This is the CLI's workhorse command and the first place real users meet pipeline errors;
output clarity (which page failed, why, what to do) is a requirement, not polish.

# Scope

`packages/core/src/glyphlab/cli/cmd_ingest.py` + tests (the `ProjectGlyphSink` adapter is
issue 15's deliverable — import it, do not reimplement).

# Detailed Requirements

1. `glyphlab ingest [FILES...] [--force] [--engine auto|potrace|potracer]`:
   - Default file set: files in `scans/` with extensions jpg/jpeg/png/heic (case-insensitive)
     **not yet recorded as processed** in `work/ingest-index.json` (keyed by sha256; rerun
     processes only new/changed files; `--all` reprocesses everything).
   - Requires `template/template.json` (exit 3 with "run `glyphlab template` first").
   - Engine from flag > config `build.vectorizer` > auto (13 selector).
   - Per file: read bytes → `ingest_scan(...)`; page-level error → print
     `file.jpg: error[E_PAGE_BLURRY]: <registry description>` and continue to next file;
     success → per-cell outcome counts + warning summary.
   - Persist each `PageIngestResult` to `work/ingest-<utcstamp>-<n>.json`; update
     `ingest-index.json` atomically.
2. Summary table (human mode) after all files:
   `file | page | extracted | empty | skipped | failed | error` and a final coverage line
   `coverage: 214/276 drawn glyphs have sources`.
3. Exit codes: all files succeeded → 0; any page-level failure → 3 (but all files still
   attempted); no input files found → 3 with hint.
4. JSON mode: array of page results (schema from 15) + coverage.
5. Tests (corpus): two-page ingest happy path; second run without changes → "nothing new";
   `--force` overwrite-accepted interplay (15 semantics surfaced: skipped list printed);
   one corrupt file among good ones → exit 3, good ones still ingested.

# Acceptance Criteria

- [ ] Incremental-by-hash behavior proven (touch/rename doesn't reprocess; content change
      does).
- [ ] Mixed success/failure run ingests good pages and exits 3 listing the bad one.
- [ ] Coverage line matches store state; JSON mode validates against report schema.

# Validation

```bash
uv run pytest packages/core/tests/cli/test_ingest.py -q
```

# Dependencies

15, 19.

# Non-goals

Watching directories, parallel file processing (sequential in v1), service upload path (31).

# Design References

DESIGN §13, §8 (orchestrator contract, report), §22 (error rendering).

# ADR-003: Paper-scan capture first, behind an input-adapter seam

- Status: Accepted (2026-07-08)
- Deciders: user (requirements interview), Fable (design)

## Context

The user wants both capture modes eventually — paper templates (scan/photo) and direct digital
ink (browser canvas / iPad) — but v1 must ship one. The choice determines v1's critical path:
an imaging pipeline versus a drawing UI plus stroke-to-outline conversion.

## Decision

- v1 implements **paper template → scan/photo** capture, with **ArUco fiducial markers**
  (`DICT_4X4_50`, 4 per page, IDs encode the page index) enabling robust phone-photo
  rectification.
- The pipeline downstream of capture consumes a `GlyphSource` protocol that yields binarized
  per-cell bitmaps (DESIGN §8.1). v2's digital-ink adapter implements the same protocol (or a
  vector fast-path that skips tracing — decided in v2).
- Cell→codepoint mapping comes exclusively from the generated `template.json` sidecar; no OCR.

## Rationale

- Works for every user with a printer + phone; no stylus hardware required (persona P1).
- The imaging pipeline is the product's differentiating core (research/02: Calligraphr's photo
  handling is its weak point); building it first de-risks the hardest part.
- Deterministic geometry (markers + sidecar) avoids fragile grid-detection heuristics and makes
  the pipeline testable with a synthetic corpus (DESIGN §18.2).

## Consequences

- v1 quality depends on print/photo conditions; mitigated by quality gates with actionable
  error codes (`E_PAGE_BLURRY` etc.) and the 100%-scale check ruler on the template.
- The web UI needs no drawing surface in v1.
- Template geometry (§7.1) becomes a versioned contract: sidecars embed everything ingest
  needs, so template layout can evolve without breaking old printed sheets.

## Alternatives rejected

- **Browser canvas first**: cleaner input but makes the web UI the critical path and defers the
  differentiating imaging work; stroke-to-outline (centerline + pen model) is its own research
  problem.
- **Plain grid without fiducials** (Calligraphr-style): simpler print, but skewed phone photos
  then need fragile line-detection; markers cost ~14 mm of margin and remove that whole failure
  class.

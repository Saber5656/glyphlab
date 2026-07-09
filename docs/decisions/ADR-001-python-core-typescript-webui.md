# ADR-001: Python core library + TypeScript web UI

- Status: Accepted (2026-07-08)
- Deciders: user (requirements interview), Fable (design)

## Context

glyphlab needs (a) image processing (rectification, binarization), (b) vector tracing, (c) font
assembly, and (d) a browser UI for the hosted service. Candidates: Python core + TS UI,
TypeScript end-to-end, Rust core + WASM.

## Decision

Core library, CLI, and service are **Python (≥ 3.11)**; the web UI is a **TypeScript/React SPA**
talking to the service over the OpenAPI contract. Monorepo with a uv workspace
(`packages/core`, `packages/service`) plus `webui/`.

## Rationale

- Font assembly quality is the product: `fontTools` (4.63) is the industry-standard,
  best-documented toolchain; no TS/Rust equivalent matches it for table correctness
  (research/01).
- OpenCV + Pillow cover the imaging stages with mature, example-rich APIs — important because
  implementation is delegated to lower-capability agents.
- The web UI cannot avoid TypeScript anyway; confining TS to a thin SPA bounds the two-language
  cost. The OpenAPI-generated client keeps the boundary mechanical.

## Consequences

- Two toolchains in CI (uv/pytest and npm/vitest+playwright); acceptable, isolated per
  directory.
- Browser-side processing (fully static hosting) is off the table for v1 — consistent with the
  chosen hosted-service model (ADR-002).
- Python's speed is sufficient given potrace runs as a native subprocess (ADR-004).

## Alternatives rejected

- **TypeScript end-to-end**: opentype.js writes fonts but the ecosystem lacks pathops-grade
  boolean ops, cu2qu, and fontbakery; glyph quality would depend on hand-rolled geometry code —
  highest correctness risk.
- **Rust + WASM**: attractive for a static site, but write-fonts et al. are younger, and the
  implementation-agent failure risk is highest; also conflicts with the hosted-service
  decision.

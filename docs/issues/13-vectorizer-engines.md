# Title

Vectorizer engines: potrace subprocess + potracer pure-Python fallback

# Summary

Implement the `VectorizerEngine` protocol with `PotraceBinaryEngine` (subprocess, preferred)
and `PotracerEngine` (optional pure-Python fallback), converting binarized cell bitmaps into
cubic-Bézier contours per DESIGN §9.1 and ADR-004.

# Context

Tracing quality defines glyph quality. The subprocess boundary is also a security control
(timeout kills adversarial trace bombs, §17.3 T5). GPL-2 isolation rules from ADR-004 apply.

# Scope

`packages/core/src/glyphlab/vectorize/{engine.py,potrace_bin.py,potrace_svg.py,
potracer_engine.py}` + tests. Adds optional extra `glyphlab[trace] = ["potracer>=0.0.4"]`
to core pyproject AND `potracer` to the dev dependency group (so CI always tests both
engines).

# Detailed Requirements

1. `engine.py`: `TraceOpts(turdsize=2, alphamax=1.0, opttolerance=0.2)`;
   `VectorizerEngine` protocol (`name: str`, `trace(bitmap: np.ndarray[bool], opts) ->
   list[Contour]` in bitmap pixel coordinates, y-down);
   `select_engine(pref: Literal["auto","potrace","potracer"]) -> VectorizerEngine`:
   auto = binary if resolvable else potracer if importable else raise
   `E_TRACE_UNAVAILABLE` with install hints in the message (`brew install potrace` /
   `pip install 'glyphlab[trace]'`).
2. `potrace_bin.py`:
   - Resolve executable: `GLYPHLAB_POTRACE_PATH` env → `shutil.which("potrace")`. Validate
     once per process with `potrace --version` (log at debug).
   - Invocation per bitmap: encode bitmap as PBM (P4) bytes in memory; run
     `subprocess.run([exe, "--backend", "svg", "--turdsize", "2", "--alphamax", "1.0",
     "--opttolerance", "0.2", "--unit", "10", "-o", "-", "-"], input=pbm, capture_output=True,
     timeout=10)` — argv list only (never `shell=True`), stdin/stdout pipes, no temp files.
     `TimeoutExpired` → `E_TRACE_TIMEOUT`; non-zero exit → `E_TRACE_TIMEOUT`?? — no:
     non-zero exit → `E_INTERNAL` with stderr excerpt (≤ 200 chars).
   - Parse the SVG output in a dedicated module `vectorize/potrace_svg.py` — this is NOT
     issue 06's restricted glyph parser (that one rejects transforms by design; potrace
     output legitimately contains them): extract `<path d>` values; parse `M/L/C/Z`
     absolute commands (quadratics never occur with the SVG backend); apply the wrapping
     `<g transform="translate(tx,ty) scale(sx,sy)">` as `p' = (tx + sx·x, ty + sy·y)`.
   - Convert to `Contour` tuples (cell-pixel space, y-down; fitting handles y-flip in 14).
   - Upstream contract: input bitmaps arrive with ≤ 64 connected components (issue 12's
     §17.3 T5 cap); add a defensive size assert (bitmap area ≤ 1200×1200 px).
3. `potracer_engine.py`: lazy `import potracer`; identical `TraceOpts` mapping via its
   pypotrace-compatible API (`Bitmap(...).trace(turdsize=..., alphamax=...,
   opttolerance=...)`); convert its curve objects (corner/curve segments) to cubics (corner →
   two line-as-cubic segments; curve → cubic as returned).
4. Equivalence: both engines on the same bitmap must yield outlines whose filled rasters
   agree ≥ 97% IoU — tested on 10 procedurally generated seeded blob bitmaps (random
   smoothed polygons rasterized with numpy/Pillow; NO corpus dependency), potracer side
   marked `slow`.
5. Thread-safety: engines must be safe for concurrent `trace` calls (no shared mutable state;
   subprocess per call).
6. Testability of selection: `select_engine` accepts injection points
   `_which: Callable[[str], str | None] = shutil.which` and `_import_potracer:
   Callable[[], ModuleType]` so tests can simulate all four availability combinations
   without uninstalling anything.
7. Performance guard: tracing 49 seeded blob bitmaps with the binary engine ≤ 5 s on CI
   (sub-budget of §21's 15 s/page).

# Acceptance Criteria

- [ ] `select_engine("auto")` picks binary when present (CI installs it per issue 02).
- [ ] Circle bitmap traces to 1 closed contour; ring (donut) to 2 with opposite orientation.
- [ ] Timeout path tested with a monkeypatched slow subprocess → `E_TRACE_TIMEOUT`.
- [ ] All four availability combinations of (binary, potracer) exercised via the injection
      points; (absent, absent) → `E_TRACE_UNAVAILABLE` whose message contains both install
      hints.
- [ ] IoU equivalence test green (runs in CI via the dev-group potracer; locally
      `-m slow`).
- [ ] 49-bitmap performance guard green.

# Validation

```bash
uv run pytest packages/core/tests/vectorize -q
uv run pytest packages/core/tests/vectorize -m slow -q     # potracer equivalence + perf
GLYPHLAB_POTRACE_PATH=/nonexistent uv run pytest packages/core/tests/vectorize/test_selection.py -q
```

# Dependencies

06 (Contour types). (No corpus/12 dependency: unit tests use synthetic bitmaps; the shared
`CellBitmap` flows in only at the orchestrator, issue 15.)

# Non-goals

Path cleanup/union (14), em-space mapping (14), parameter auto-tuning (KU-1).

# Design References

DESIGN §9.1, §17.3 T5, §21 (trace within page budget), ADR-004.

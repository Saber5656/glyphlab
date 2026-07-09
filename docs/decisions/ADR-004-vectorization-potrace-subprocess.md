# ADR-004: Vectorization via potrace subprocess, pure-Python fallback

- Status: Accepted (2026-07-08)
- Deciders: Fable (design), per research/01

## Context

Binarized cell bitmaps must become Bézier outlines. Candidates: the `potrace` C binary
(GPL-2), `pypotrace` C bindings (stale, build problems), `potracer` pure-Python port (GPL-2,
~500× slower), or a hand-rolled tracer (out of the question for quality).

## Decision

A `VectorizerEngine` protocol with two implementations, selected at runtime (`vectorizer =
"auto"`):

1. **`PotraceBinaryEngine`** (preferred): invokes the `potrace` executable via
   `subprocess.run` with a fixed argument vector (never a shell), stdin/stdout pipes, and a
   10-second timeout. Guaranteed present in the service Docker image (`apt-get install
   potrace`); locally via Homebrew/apt.
2. **`PotracerEngine`**: pure-Python `potracer`, installed only via the optional extra
   `glyphlab[trace]`, imported lazily. Slow but removes any native-binary requirement for
   pip-only users.

Identical tracing parameters for both: `turdsize=2, alphamax=1.0, opttolerance=0.2`
(calibration tracked as KU-1).

## License analysis

potrace and potracer are GPL-2. glyphlab remains MIT because: the binary is invoked as a
separate process (no linking, mere aggregation), and potracer is an *optional*, user-installed
dependency imported at runtime, not distributed with glyphlab. README must state: the Docker
image *does* aggregate GPL-2 potrace — its source offer is satisfied by upstream Debian
packaging; fonts produced are unaffected by GPL in any case.

## Consequences

- Deterministic, battle-tested outlines; performance budget (≤ 15 s/page) achievable with the
  binary engine.
- Two engines must produce equivalent (not byte-identical) output; golden tests pin the binary
  engine, and a tolerance-based equivalence test covers potracer.
- Subprocess boundary doubles as a security boundary (timeout kills trace bombs, T5).

## Alternatives rejected

- **pypotrace bindings**: installation failures across OSes — unacceptable for a pip-installed
  tool.
- **potracer as the only engine**: 48-cell page would take minutes; fine as fallback only.
- **skimage marching squares + curve fitting**: reinvents potrace poorly.

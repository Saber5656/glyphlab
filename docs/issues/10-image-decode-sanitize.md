# Title

Ingest S1: image decode & sanitize

# Summary

Implement the untrusted-bytes entry stage (DESIGN §8.2 S1): format sniffing, size/pixel
pre-checks, safe decode of JPEG/PNG/HEIC, EXIF orientation, alpha flattening, grayscale
conversion — with the exact failure codes.

# Context

This is trust boundary B2's front door (§17.3 T1). The CLI and the service **worker** call
`decode_scan` on raw bytes; the service upload endpoint (31) calls only the cheap
`sniff_format` at request time — full decode never runs on the request path. Nothing
upstream is trusted.

# Scope

`packages/core/src/glyphlab/ingest/decode.py` + tests. Adds core deps: `pillow`,
`pillow-heif`.

# Detailed Requirements

1. Public API (both exported from `glyphlab.ingest.decode`):
   - `sniff_format(head: bytes) -> Literal["jpeg", "png", "heic"] | None` — pure
     magic-byte sniffer over the first 32 bytes (spec in req 2b); used by the service
     upload endpoint (issue 31) without decoding.
   - `decode_scan(data: bytes, *, max_bytes=12*2**20, max_pixels=36_000_000) ->
     np.ndarray` (uint8 grayscale, y-down; §8.2 S1 output) raising `GlyphlabError`
     subclasses with codes `E_IMG_TOO_LARGE`, `E_IMG_FORMAT`, `E_IMG_DECODE`.
2. Order of checks (fail fast, cheapest first):
   a. `len(data) > max_bytes` → `E_IMG_TOO_LARGE`.
   b. Magic-byte sniff via `sniff_format`: JPEG = bytes 0–2 `FF D8 FF`; PNG = bytes 0–7
      `89 50 4E 47 0D 0A 1A 0A`; HEIC/HEIF = ISO BMFF with bytes 4–7 == `ftyp` AND major
      brand (bytes 8–11) ∈ {`heic`, `heix`, `mif1`, `msf1`}. `None` → `E_IMG_FORMAT`.
      Extension is irrelevant; never trust it.
   c. Header-only dimension probe (`Image.open` lazy + `.size` before `load()`); w*h >
      max_pixels → `E_IMG_TOO_LARGE`.
   d. Set `Image.MAX_IMAGE_PIXELS = max_pixels` (module import time, belt-and-braces) —
      `DecompressionBombError` mapped to `E_IMG_TOO_LARGE`.
   e. Full decode inside `try` → any `OSError`/pillow error → `E_IMG_DECODE`.
3. `pillow_heif.register_heif_opener()` at module import; HEIC absence (import failure)
   must degrade gracefully: sniffing still returns `"heic"` and `decode_scan` raises
   `E_IMG_FORMAT` with `detail={"reason": "heic_unavailable"}` (uses issue 06's
   `GlyphlabError.detail`; KU-5 posture).
4. Post-decode normalization per §8.2 S1: `ImageOps.exif_transpose` (orientation),
   composite alpha over white, convert to `L` (grayscale), downscale longest side to
   ≤ 4500 px (LANCZOS) — caps memory before rectification; return numpy array.
5. No filesystem access; bytes in → array out. No subprocesses. Runs under the worker's job
   timeout; no internal threading.
6. Fuzz-ish tests: truncated JPEG, PNG with 100kx100k header (bomb), zip-renamed-to-jpg, EXIF
   orientations 1–8 (tiny fixtures), 16-bit PNG, CMYK JPEG, HEIC fixture (small, generated
   via pillow-heif in a test-skip-if-unavailable block).

# Acceptance Criteria

- [ ] All malicious/degenerate fixtures rejected with the exact specified codes; nothing
      raises a non-`GlyphlabError` exception.
- [ ] EXIF orientation 6 fixture comes out rotated correctly (assert pixel positions).
- [ ] 13 MiB file rejected before any decode work (assert via monkeypatched `Image.open`
      call-count = 0).
- [ ] Peak RSS during decode of the 36 MP boundary fixture < 400 MiB (`psutil` added to
      the dev dependency group; test marked `slow`).

# Validation

```bash
uv run pytest packages/core/tests/ingest/test_decode.py -q
```

# Dependencies

01, 06.

# Non-goals

Marker detection (11), service HTTP validation (31 — it reuses this), any retry logic.

# Design References

DESIGN §8.2 S1, §17.3 T1, §17.4 upload rules, §2.4 KU-5.

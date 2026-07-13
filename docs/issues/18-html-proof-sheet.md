# Title

HTML proof sheet generator

# Summary

Generate the self-contained `proof.html` of DESIGN §11.3: embedded WOFF2 (data URI), full
glyph grid with status/warning badges, pangram samples, missing-glyph list, and build
metadata — with strict output escaping and a no-external-request CSP.

# Context

The proof sheet is how users (CLI persona especially) judge their font, and it doubles as the
"preview" for anyone without the web UI. It renders untrusted strings (project name), so
escaping rules are part of the spec, not a nicety.

# Scope

`packages/core/src/glyphlab/report/proof.py` + a single Jinja-free template (stdlib
`string.Template` or f-string builder — no new deps) + tests.

# Detailed Requirements

1. `generate_proof(out_path, *, woff2_bytes, project: ProjectConfig, charset,
   statuses: dict[int, tuple[GlyphStatus, list[GlyphWarning]]] (issue 06 types),
   qa: QAReport (issue 17 type), meta: ProofMeta) -> Path` where
   `ProofMeta = {charset_id: str, charset_version: int, version: int, built_at_iso: str,
   counts: dict[str, int]}` (defined in `report/proof.py`).
2. Document structure:
   - `<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src
     'unsafe-inline'; font-src data:; img-src data:">` and `<meta charset="utf-8">`.
   - `@font-face { font-family: "GlyphlabProof"; src: url(data:font/woff2;base64,...) }`.
   - Header: family name, charset id@version, build date (UTC ISO), glyph counts by status,
     QA pass/fail badge (+ FAIL check ids if any).
   - Glyph grid: charset order; each cell shows the glyph rendered in the font at 42 px, the
     codepoint label, status color (auto=blue, accepted=green, rejected=red strikethrough,
     missing=gray placeholder box), warning badges (§9.5 codes as small chips with
     `title=` tooltips).
   - Samples section, exact strings (module constants; goldens depend on them):
     `IROHA = "いろはにほへと ちりぬるを わかよたれそ つねならむ うゐのおくやま けふこえて あさきゆめみし ゑひもせす"`
     (spaces as shown; historic kana ゐ/ゑ are NOT in the kana preset and thus render as
     fallback holes — deliberately kept to demonstrate missing-glyph behavior, noted in a
     caption), `PANGRAM = "The quick brown fox jumps over the lazy dog 0123456789"`,
     `MIXED = "きょうは「Glyphlab」でフォントを作った。ローマ字とかなが、ひとつの文で・ながく・つづく！"`
     — each at 3 sizes (16/24/36 px).
   - Missing list: comma-separated literal chars + codepoints.
3. Escaping: ALL interpolations pass through `html.escape(..., quote=True)`; glyphs
   rendered as text content via `&#xXXXX;` numeric refs (never raw user strings); a unit
   test feeds `name = '<script>alert(1)</script>"'` and asserts (a) the output contains no
   `<script` substring case-insensitively, and (b) the name appears exactly once, as the
   escaped form `&lt;script&gt;alert(1)&lt;/script&gt;&quot;`.
4. Self-containment test: parse output with `html.parser`; assert zero `src`/`href`
   attributes that are not `data:` URIs; file size < 5 MiB for 278 glyphs.
5. Missing/rejected glyphs must not silently vanish: placeholder boxes keep grid positions.
6. Rendering correctness is not machine-verified (no headless browser here — Playwright
   covers the web UI separately); structural HTML assertions + one committed golden file
   (small ascii-only build) suffice. A pytest fixture additionally writes
   `packages/core/tests/artifacts/proof-sample.html` (path gitignored) so a human can open
   it — an optional, non-gating convenience.

# Acceptance Criteria

- [ ] XSS test green (both assertions of req 3); CSP meta present; zero external
      references (automated check).
- [ ] Golden ascii proof matches snapshot (normalized whitespace).
- [ ] Grid contains exactly `len(charset)` cells; statuses/badges match inputs.

# Validation

```bash
uv run pytest packages/core/tests/report -q
open packages/core/tests/artifacts/proof-sample.html  # macOS spot check
```

# Dependencies

04, 16 (woff2 bytes for the golden sample), 17 (`QAReport` type).

# Non-goals

Web UI preview page (43), PDF proof, per-glyph editing links.

# Design References

DESIGN §11.3, §17.3 T7 (escaping), §9.5 (warning chips), §16.4 (no-external-assets posture).

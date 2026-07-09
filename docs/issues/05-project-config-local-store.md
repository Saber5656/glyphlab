# Title

Project config schema (`glyphlab.toml`) & local project store

# Summary

Implement `glyphlab.project`: the pydantic-validated project config (DESIGN §12.2), the local
project directory layout (§12.1), atomic `glyphs/status.json` persistence, and the custom
charset TOML loader (CLI-only feature).

# Context

The CLI operates on a project directory; the core pipeline reads/writes through this store. It
is also where user-input validation for names begins (XSS/name constraints, §17.4).

# Scope

`packages/core/src/glyphlab/project/{config.py,store.py,charset_file.py}` + tests. No CLI
commands here (19/20).

# Detailed Requirements

1. `config.py`: pydantic v2 models mirroring §12.2 exactly:
   - `schema` const `"glyphlab.project/1"`.
   - `project.name`: 1–64 chars after NFC normalization; reject control chars (`C0/C1`) and
     leading/trailing whitespace.
   - `project.family_name`: regex `^[A-Za-z0-9][A-Za-z0-9 \-]{0,30}$` (TTF name constraint,
     §10.4).
   - `project.charset`: preset id or relative path ending `.toml`; `project.version`: int ≥ 1.
   - `build.include_unreviewed` (default true), `build.vectorizer` in {auto,potrace,potracer}.
   - Loader `load_config(path) -> ProjectConfig` raising `ConfigError` with line/field detail;
     writer `write_config` producing stable, commented TOML.
2. `store.py`: `ProjectStore(root: Path)` with:
   - `init(config)` — create the §12.1 **directories** (`template/`, `scans/`, `work/`,
     `glyphs/`, `build/`) plus `glyphlab.toml` and an empty `glyphs/status.json`; refuse
     non-empty dir (`E_VALIDATION`). Files inside those directories (template PDF, SVGs,
     reports, fonts) are produced by later commands, not by `init`.
   - `glyph_svg_path(cp) -> Path` (`glyphs/U+XXXX.svg`, uppercase hex, 4–6 digits).
   - `read_status() / write_status(dict)` — JSON schema
     `{ "U+3042": {"status": "auto", "warnings": ["LOW_INK"], "source": {"upload": "...", "cell": 7}} }`;
     writes atomic: write to `status.json.tmp` in same dir, `os.replace`. Concurrent-safe
     enough for single-user CLI (documented).
   - `list_scans() -> list[Path]` — files in `scans/` whose extension (case-insensitive)
     is one of `.jpg .jpeg .png .heic` (the §17.4 upload formats; same set issue 22 uses),
     sorted by name; other files ignored silently. `ingest_report_path(ts)`, `build_dir()`
     helpers.
3. `charset_file.py`: custom charset TOML (schema: `name`, `version`, `chars = ["U+0041",
   "U+3042-U+3044", "あ"]`): parse entries as single char literal, `U+XXXX`, or inclusive
   range; build a `CharsetSpec` with `script_class` inferred by Unicode block
   (Hiragana/Katakana blocks → kana; CJK symbols U+3000–U+303F → punct_ja; else latin) and
   every char `drawn=True` except U+0020/U+3000. Enforce §17.4 exactly: file size ≤ 4096
   bytes; expanded set ≤ **500 drawn chars** (template marker budget, §7.1); every entry a
   valid Unicode scalar value (surrogates and > U+10FFFF rejected; ranges must be
   ascending).
4. All paths derived via `Path` joins on validated components; never interpolate user strings
   into paths except the project root the user supplied.

# Acceptance Criteria

- [ ] Config round-trip: write → load → identical model; bad inputs produce field-precise
      errors (name with `\x00`, 65-char name, name `" x"` with leading space, family name
      `日本語` all rejected).
- [ ] `init` creates exactly the 5 directories + 2 files listed above; second `init` on the
      same dir fails.
- [ ] `write_status` is atomic (test: crash-inject via monkeypatched `os.replace` leaves
      original intact).
- [ ] Charset file: `"U+3042-U+3044"` expands to 3 kana-class chars; a 501-drawn-char set is
      rejected; a 4097-byte file is rejected; `"U+D800"` (surrogate) is rejected.
- [ ] `list_scans` picks up `.JPG` and `.heic`, ignores `.txt` and `.svg`.

# Validation

```bash
uv run pytest packages/core/tests/project -q
```

# Dependencies

01, 04.

# Non-goals

CLI wiring (19/20), service-side persistence (27/28), template/sidecar files (07).

# Design References

DESIGN §12 (layout, config), §6.2 (custom charsets CLI-only), §17.4 (input rules), §10.4
(family name constraint).

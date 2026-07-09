# Title

Charset model & presets: `ascii`, `kana`, `ja-basic-v1`

# Summary

Implement `glyphlab.charset`: the `CharDef`/`CharsetSpec` frozen models, the three v1 presets
with exact codepoint contents from DESIGN §6.1, script-class assignment, synthesized-glyph
rules, and lookup/iteration APIs used by template, fitting, font build, and the service.

# Context

The charset is the contract that template pages, ingest cell mapping, fitting rules, and cmap
coverage all derive from. Exactness here is non-negotiable; a off-by-one range corrupts every
downstream artifact.

# Scope

`packages/core/src/glyphlab/charset/{model.py,presets.py,__init__.py}` + exhaustive tests.
Custom charset TOML loading is issue 05 (config) territory — here only the in-memory model.

# Detailed Requirements

1. `model.py`: `CharDef(codepoint: int, script_class: Literal["latin","kana","punct_ja"],
   drawn: bool)`, `CharsetSpec(charset_id: str, version: int, chars: tuple[CharDef, ...])`,
   both frozen dataclasses. `CharsetSpec` invariants enforced in `__post_init__`: codepoints
   strictly ascending, unique, all valid Unicode scalars.
2. `CharsetSpec` API: `codepoints() -> tuple[int,...]`, `drawn_chars() -> tuple[CharDef,...]`,
   `get(cp) -> CharDef | None`, `__len__`, `__contains__`.
3. `presets.py`: `PRESETS: dict[str, CharsetSpec]`. All specs store chars in **strictly
   ascending codepoint order** (DESIGN §6.1 canonical ordering). Exact contents:
   - `ascii` v1: U+0020..U+007E inclusive (95 encoded / 94 drawn; `drawn=False` only for
     U+0020). All `latin`.
   - `kana` v1 (ascending: U+3000, U+3001, U+3002, U+300C, U+300D, U+3041..U+3096,
     U+30A1..U+30FA, U+30FB, U+30FC): `kana` class = U+3041..U+3096 (86), U+30A1..U+30FA
     (90), U+30FC (1); `punct_ja` class = U+3000 (`drawn=False`), U+3001, U+3002, U+300C,
     U+300D, U+30FB. Total **183 encoded, 182 drawn**.
   - `ja-basic-v1` v1: set union of `ascii` and `kana`, ascending. Total **278 encoded,
     276 drawn**.
4. `get_preset(charset_id: str) -> CharsetSpec` raising `UnknownCharsetError(ValueError)`
   defined in this module. (Its mapping into the §22 error registry as `E_VALIDATION`
   detail happens in issue 06, which depends on this issue.)
5. Synthesized advances live with the charset (used by font build):
   `SYNTHESIZED_ADVANCES = {0x0020: 500, 0x3000: 1000}`.
6. Preset snapshot guard: `packages/core/tests/charset/snapshots/presets.json` maps
   `charset_id` → `{"version": N, "sha256": hex}` where the hash is SHA-256 of
   `f"{charset_id}:{version}:" + ",".join(f"{cp:04X}" for cp in codepoints)`. The test
   recomputes and compares; a mismatch message must instruct: "presets are immutable —
   bump the version and update the snapshot deliberately".

# Acceptance Criteria

- [ ] Counts exactly: ascii 95/94; kana 183/182; ja-basic-v1 278/276.
- [ ] Boundary codepoints present: U+0020, U+007E, U+3041, U+3096, U+30A1, U+30FA, U+30FB,
      U+30FC, U+3000, U+3001, U+3002, U+300C, U+300D. Absent: U+007F, U+3040, U+3097,
      U+30FD, U+30FE, U+309B, U+309C.
- [ ] Codepoints strictly ascending in every preset (unit test).
- [ ] Script classes match DESIGN §6.1 assignment for every char (property test over ranges).
- [ ] Snapshot test in place with the exact hash formula above.

# Validation

```bash
uv run pytest packages/core/tests/charset -q
uv run mypy packages/core/src/glyphlab/charset
uv run python -c "from glyphlab.charset import get_preset; s=get_preset('ja-basic-v1'); print(len(s), sum(c.drawn for c in s.chars))"
# expect: 278 276
```

# Dependencies

01.

# Non-goals

Custom charset TOML parsing (05), kanji presets (v2 D2), template geometry (07).

# Design References

DESIGN §6 (exact contents, ordering & rules), §5 (CharDef), §10.2 (font glyph order is
`.notdef` then ascending codepoint — the same order this module stores).

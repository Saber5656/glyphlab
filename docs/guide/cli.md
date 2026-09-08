# CLI guide

The CLI performs no network I/O while processing projects. Install Python 3.11+,
`glyphlab[trace,qa]`, and preferably native `potrace`. Global flags go **before** the command:

```bash
glyphlab --project myhand --json status
```

| Command | Main options and behavior |
| --- | --- |
| `new NAME` | `--dir PATH`, `--family-name ASCII`, `--charset PRESET_OR_TOML`; refuses a nonempty directory |
| `charset list` | Lists preset versions, encoded/drawn counts and page counts |
| `charset show ID` | `--codepoints` prints each character |
| `template` | Idempotent; `--regenerate --yes` changes the template id and requires reprinting; `--open` opens the PDF |
| `ingest [FILES...]` | Defaults to scans/; content hashes skip unchanged files; `--all` rescans; `--force` also overwrites accepted glyphs; `--engine auto/potrace/potracer` |
| `status` | Coverage and warning counts; `--missing`, `--warned` for details |
| `accept SET...` / `reject SET...` | Literal characters, `U+0041`, `U+0041-U+005A`, `--all-auto`, or `--all-warned LOW_INK` |
| `build` | `--accepted-only` / `--include-unreviewed`, `--out DIR`, `--skip-bakery`; only `--completer none` in v1 |

Missing glyphs cannot be accepted. Accepting a glyph protects it against ordinary re-ingest.
Editing `glyphs/U+XXXX.svg` is supported only within the restricted M/L/C/Z path format;
transforms, embedded resources and scripts are rejected. Back up before editing.

## Project state

`glyphlab.toml`, `template/`, and `glyphs/` are authoritative project state. `work/` is
disposable intermediate data, including the incremental ingestion index. `build/` is
regenerated. Preserve scans yourself if you want to reprocess them later.

The family name is 1–31 ASCII letters/digits/spaces/hyphens, beginning with an alphanumeric
character. The display name supports Japanese (1–64 NFC characters, no controls or edge
whitespace). For a Japanese display name, provide `--family-name` and `--dir` explicitly.

## Custom charset (CLI only)

Create a UTF-8 TOML file, no larger than 4096 bytes:

```toml
name = "my-small-set"
version = 1
chars = ["U+0020", "U+0041-U+0043", "あ", "U+3000"]
```

Use `--charset /absolute/path/custom.toml`, or a relative path resolved from the project
root. Ranges must ascend, all entries must be Unicode scalar values, and no more than
500 drawn characters are permitted. Spaces U+0020/U+3000 are synthesized. Keep the
charset file available and immutable for the lifetime of its template.

## Errors and JSON

Exit 0 means success; 1 unexpected failure; 2 command usage; 3 invalid input or page;
4 failed font QA. `--verbose` includes detailed diagnostics on stderr. With `--json`,
stdout has one envelope: `{ "ok": true, "data": ... }` or
`{ "ok": false, "error": { "code": ..., "message": ..., "detail": ... } }`.
A mixed ingest run reports every page and returns exit 3 if any page failed; successful
pages remain saved. Font QA failure keeps diagnostics and proof files locally.

The mandatory structural gate checks coverage, advances, bounds and font tables. The
universal Font Bakery gate is enabled by default. Its narrowly justified exceptions
are recorded in `qa/allowlist.toml`; `--skip-bakery` is for local inspection and is not
available for hosted builds.

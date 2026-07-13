# Title

CLI commands: `new`, `charset list`, `charset show`

# Summary

Implement project creation and charset inspection commands per DESIGN §13, on top of the
issue-19 framework and issue-05 store.

# Context

`new` is the first command every CLI user runs; `charset show` is how users see exactly what
they will be handwriting (and how many pages).

# Scope

`packages/core/src/glyphlab/cli/{cmd_new.py,cmd_charset.py}` + tests.

# Detailed Requirements

1. `glyphlab new NAME [--charset ja-basic-v1] [--family-name X] [--dir PATH]`:
   - Target dir = `--dir` or `./<slug>` (slug: NAME lowercased, spaces→`-`, strip chars
     outside `[a-z0-9\-]`); an **empty slug** (e.g. Japanese-only NAME) without `--dir` →
     exit 3 telling the user to pass `--dir`; existing non-empty target → exit 3.
   - `--family-name` default: ASCII-only transliteration is NOT attempted; if NAME fails the
     §12.2 family regex, require the flag explicitly (error message explains the TTF
     constraint; e.g. Japanese NAME needs `--family-name`).
   - `--charset` must be a preset id or a `.toml` path (custom charset via issue 05's
     loader, which enforces the §17.4 limits — file ≤ 4096 bytes, ≤ 500 drawn chars,
     valid scalars; loader errors surface with exit 3). Relative paths are stored as
     given and resolved against the project root at load time; absolute paths stored
     absolute.
   - Calls `ProjectStore.init`; prints next-steps hint (template → write → ingest); JSON mode
     returns `{root, charset, pages}` (pages via 07 layout).
2. `glyphlab charset list`: table `id | version | encoded | drawn | pages` for all presets
   (pages from `compute_layout`).
3. `glyphlab charset show ID [--codepoints]`: summary (counts per script class, page count);
   with `--codepoints`, one line per char: `U+3042 あ kana drawn`. Works for preset ids and
   `.toml` paths.
4. All output through issue-19 render helpers; errors through `cli_guard`.

# Acceptance Criteria

- [ ] `new` creates issue 05's `init` layout (5 dirs + glyphlab.toml + status.json;
      template files belong to issue 21) with valid config; rerun on same dir exits 3.
- [ ] Japanese NAME without `--family-name` exits 3 with the explanatory message; Japanese
      NAME without `--dir` exits 3 (empty slug).
- [ ] `charset list` shows ja-basic-v1 with 278/276/6.
- [ ] `charset show ja-basic-v1 --codepoints --json | jq '.data.chars | length'` == 278.
- [ ] Custom charset over the §17.4 limits surfaces the loader error with exit 3.
- [ ] JSON variants parse and carry the same data.

# Validation

```bash
cd $(mktemp -d)
uv run glyphlab new "test font" --family-name TestFont
uv run glyphlab charset show ja-basic-v1 --codepoints --json | jq '.data.chars | length'   # 278
uv run pytest packages/core/tests/cli/test_new_charset.py -q
```

# Dependencies

04, 05, 07 (page counts), 19.

# Non-goals

Template generation (21), interactive prompts (flags only in v1).

# Design References

DESIGN §13, §12.1–12.2, §6.

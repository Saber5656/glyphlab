# Title

CLI command: `template`

# Summary

Implement `glyphlab template`: generate (or regenerate) the project's template PDF + sidecar
into `template/`, per DESIGN §13.

# Context

Bridges project config to the issue-07/08 template stack; idempotency matters because
regenerating changes the sidecar while already-printed sheets keep their old geometry —
an undetectable mismatch (markers encode only page indexes, DESIGN §7.2 known limitation),
so the command must be loudly explicit about when reprinting is required.

# Scope

`packages/core/src/glyphlab/cli/cmd_template.py` + tests.

# Detailed Requirements

1. `glyphlab template [--regenerate] [--yes] [--open]`:
   - Loads project (19 helper); resolves charset (preset or custom file).
   - If `template/template.json` exists and `--regenerate` absent: verify it matches the
     project charset (id+version) AND that the sibling PDF exists; full match → print
     "template up to date" + paths, exit 0 (idempotent no-op); charset mismatch → render
     `E_TEMPLATE_MISMATCH` (exit 3 via issue 19's mapping) with a `--regenerate` hint;
     missing PDF with valid sidecar → regenerate the PDF only, keeping the template_id.
   - Generation: new uuid4 `template_id`; call issue-08 `generate_template` (project name
     flows through 08's §7.3 sanitizer; custom charsets already validated by 05's §17.4
     loader); print page count, PDF path, and the printing instructions line (100% scale
     warning).
   - `--regenerate` overwrites PDF + sidecar (new template_id) and warns: **previously
     printed sheets must be thrown away and reprinted** (geometry mismatch is undetectable
     — DESIGN §7.2). Interactive `y/N` confirm; non-TTY (or `--yes`): `--yes` proceeds,
     absence of `--yes` in non-TTY → exit 3 with "pass --yes to confirm".
   - `--open` (macOS/Linux best-effort): `open`/`xdg-open` the PDF; failures non-fatal.
2. JSON mode via issue 19's envelope: `data = {pdf, sidecar, template_id, pages,
   regenerated: bool}`.
3. Tests: fresh project → files created, sidecar charset matches; second run no-op with same
   template_id; config charset swap → exit 3 with `E_TEMPLATE_MISMATCH`; deleted PDF +
   valid sidecar → PDF restored, template_id unchanged; `--regenerate --yes` → new
   template_id; `--regenerate` without `--yes` under non-TTY → exit 3; JSON envelope shape.

# Acceptance Criteria

- [ ] Idempotency + mismatch + PDF-restore + regenerate flows all tested.
- [ ] Generated PDF/sidecar identical in structure to direct issue-08 output (same code
      path, no duplication).
- [ ] `--yes` required for non-interactive regenerate (CI-safe); JSON envelope covered.

# Validation

```bash
d=$(mktemp -d) && cd "$d"
uv run --project ~/dev/glyphlab glyphlab new demo --family-name Demo && cd demo
uv run --project ~/dev/glyphlab glyphlab template
uv run --project ~/dev/glyphlab glyphlab template   # second run prints "up to date"
cd ~/dev/glyphlab && uv run pytest packages/core/tests/cli/test_template.py -q
```

# Dependencies

07, 08, 19.

# Non-goals

Printing calibration (KU-7), template layout options (fixed geometry in v1).

# Design References

DESIGN §13, §7 (template contract), §8.2 S3 (`E_PAGE_UNKNOWN` linkage).

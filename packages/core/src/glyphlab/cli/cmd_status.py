"""Coverage derived from charset and persistent review state."""

from collections import Counter

import typer

from glyphlab.cli.context import current, require_project, resolve_charset
from glyphlab.cli.render import cli_guard, success


def compact_ranges(codepoints: list[int]) -> str:
    if not codepoints:
        return ""
    points = sorted(set(codepoints))
    result = []
    start = end = points[0]
    for cp in points[1:]:
        if cp == end + 1:
            end = cp
            continue
        result.append(f"U+{start:04X}" + (f"-U+{end:04X}" if end != start else ""))
        start = end = cp
    result.append(f"U+{start:04X}" + (f"-U+{end:04X}" if end != start else ""))
    return ", ".join(result)


@cli_guard
def status(missing: bool = False, warned: bool = False) -> None:
    ctx = current()
    config, store = require_project(ctx)
    charset = resolve_charset(config.project.charset, ctx.project_root)
    saved = store.read_status()
    counts = dict.fromkeys(("missing", "auto", "accepted", "rejected"), 0)
    warnings: Counter[str] = Counter()
    glyphs = {}
    absent = []
    for char in charset.chars:
        if not char.drawn:
            continue
        key = f"U+{char.codepoint:04X}"
        entry = saved.get(key, {"status": "missing", "warnings": []})
        state = str(entry["status"])
        codes = entry.get("warnings", [])
        counts[state] += 1
        warnings.update(codes)
        glyphs[key] = {"status": state, "warnings": codes}
        if state == "missing":
            absent.append(char.codepoint)
    counts["total"] = sum(counts.values())
    human = f"{config.project.name} — {charset.charset_id}@{charset.version}\n"
    human += "\n".join(f"{state}: {count}" for state, count in counts.items())
    human += f"\nSynthesized: {len(charset.chars) - counts['total']}"
    if missing:
        human += "\nMissing: " + compact_ranges(absent)
    if warned:
        human += "\n" + "\n".join(
            f"{cp} {entry['warnings']}" for cp, entry in glyphs.items() if entry["warnings"]
        )
    success({"counts": counts, "warnings": dict(warnings), "glyphs": glyphs}, human)


def register(app: typer.Typer) -> None:
    app.command()(status)

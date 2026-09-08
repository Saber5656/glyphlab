"""Explicit review transitions over validated Unicode sets."""

import re
from typing import Annotated

import typer

from glyphlab.cli.context import current, require_project, resolve_charset
from glyphlab.cli.render import cli_guard, success
from glyphlab.errors import GlyphlabError
from glyphlab.model import GlyphWarning


def parse_codepoints(values: list[str], allowed: set[int]) -> set[int]:
    points: set[int] = set()
    for value in values:
        match = re.fullmatch(r"U\+([0-9A-Fa-f]{4,6})(?:-U\+([0-9A-Fa-f]{4,6}))?", value)
        if match:
            start = int(match[1], 16)
            end = int(match[2], 16) if match[2] else start
            if start > end or end > 0x10FFFF or end - start > 500:
                raise GlyphlabError("E_VALIDATION", f"Invalid codepoint range: {value}")
            points.update(range(start, end + 1))
        elif value.startswith("U+"):
            raise GlyphlabError("E_VALIDATION", f"Invalid codepoint: {value}")
        else:
            points.update(map(ord, value))
    invalid = points - allowed
    if invalid:
        raise GlyphlabError(
            "E_VALIDATION",
            "Codepoints outside charset: " + ", ".join(f"U+{cp:04X}" for cp in sorted(invalid)),
        )
    return points


def review(values: list[str], all_auto: bool, all_warned: str | None, target: str) -> None:
    ctx = current()
    config, store = require_project(ctx)
    charset = resolve_charset(config.project.charset, ctx.project_root)
    saved = store.read_status()
    points = parse_codepoints(values, {c.codepoint for c in charset.chars if c.drawn})
    if all_warned and all_warned not in {w.value for w in GlyphWarning}:
        raise GlyphlabError("E_VALIDATION", f"Unknown warning: {all_warned}")
    for saved_key, saved_entry in saved.items():
        if (all_auto and saved_entry["status"] == "auto") or (
            all_warned and all_warned in saved_entry.get("warnings", [])
        ):
            points.add(int(saved_key[2:], 16))
    if not values and not all_auto and not all_warned:
        raise typer.BadParameter("Provide codepoints, --all-auto, or --all-warned")
    absent = []
    changed = already = 0
    for cp in sorted(points):
        key = f"U+{cp:04X}"
        entry = saved.get(key)
        if entry is None or entry["status"] == "missing":
            absent.append(key)
        elif entry["status"] == target:
            already += 1
        else:
            entry["status"] = target
            changed += 1
    store.write_status(saved)
    if absent:
        raise GlyphlabError(
            "E_VALIDATION",
            f"{target} {changed}, already {already}, missing {len(absent)}",
            detail={"missing": absent},
        )
    success(
        {"changed": changed, "already": already, "missing": absent},
        f"{target} {changed}, already {already}, {len(points)} matched",
    )


@cli_guard
def accept(
    values: Annotated[list[str] | None, typer.Argument()] = None,
    all_auto: bool = False,
    all_warned: str | None = None,
) -> None:
    review(values or [], all_auto, all_warned, "accepted")


@cli_guard
def reject(
    values: Annotated[list[str] | None, typer.Argument()] = None,
    all_auto: bool = False,
    all_warned: str | None = None,
) -> None:
    review(values or [], all_auto, all_warned, "rejected")


def register(app: typer.Typer) -> None:
    app.command()(accept)
    app.command()(reject)

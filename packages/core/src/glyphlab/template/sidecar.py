"""Versioned template serialization with internal consistency validation."""

import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from uuid import UUID

from glyphlab.charset import CharsetSpec
from glyphlab.errors import GlyphlabError

from .layout import Cell, ContentGeometry, GridGeometry, TemplateLayout, TemplatePage


@dataclass(frozen=True)
class TemplateSidecar(TemplateLayout):
    template_id: str
    charset_id: str
    charset_version: int
    schema: str = "glyphlab.template/1"


def validate_sidecar(sidecar: TemplateSidecar, expected_charset: CharsetSpec | None = None) -> None:
    def reject(message: str) -> None:
        raise GlyphlabError("E_TEMPLATE_MISMATCH", message)

    if sidecar.schema != "glyphlab.template/1" or not 1 <= len(sidecar.pages) <= 12:
        reject("Unsupported or empty template")
    try:
        UUID(sidecar.template_id)
    except (ValueError, TypeError):
        reject("Invalid template identifier")
    seen: set[int] = set()
    indices: set[int] = set()
    drawn = {c.codepoint for c in expected_charset.drawn_chars()} if expected_charset else None
    if expected_charset and (sidecar.charset_id, sidecar.charset_version) != (
        expected_charset.charset_id,
        expected_charset.version,
    ):
        reject("Template charset does not match project")
    for p in sidecar.pages:
        if (
            p.index in indices
            or not 0 <= p.index < 12
            or p.aruco_ids != tuple(range(4 * p.index, 4 * p.index + 4))
        ):
            reject("Invalid page index or marker IDs")
        indices.add(p.index)
        g, c = p.grid_mm, p.content_mm
        numbers = [
            g.x0,
            g.y0,
            g.cell,
            g.label_h,
            g.gap,
            c.x0,
            c.y0,
            c.x1,
            c.y1,
            c.marker,
        ]
        if not all(isinstance(v, (int, float)) and math.isfinite(v) for v in numbers):
            reject("Non-finite geometry")
        if not (
            isinstance(g.cols, int)
            and isinstance(g.rows, int)
            and g.cols > 0
            and g.rows > 0
            and min(g.cell, g.label_h, g.gap, c.marker) > 0
        ):
            reject("Non-positive grid geometry")
        if not (
            0 <= c.x0 < c.x1 <= 210
            and 0 <= c.y0 < c.y1 <= 297
            and c.x0 <= g.x0
            and c.y0 <= g.y0
            and g.x0 + g.cols * g.cell + (g.cols - 1) * g.gap <= c.x1
            and g.y0 + g.rows * (g.cell + g.label_h) + (g.rows - 1) * g.gap <= c.y1
        ):
            reject("Grid is outside content area")
        positions: set[tuple[int, int]] = set()
        for cell in p.cells:
            pos = (cell.row, cell.col)
            if pos in positions or not (0 <= cell.row < g.rows and 0 <= cell.col < g.cols):
                reject("Duplicate or out-of-range cell")
            positions.add(pos)
            cp = cell.codepoint
            if cp is None:
                continue
            if (
                not isinstance(cp, int)
                or cp in seen
                or not 0 <= cp <= 0x10FFFF
                or 0xD800 <= cp <= 0xDFFF
                or (drawn is not None and cp not in drawn)
            ):
                reject("Duplicate or unexpected codepoint")
            seen.add(cp)


def write_sidecar(
    path: Path, layout: TemplateLayout, template_id: UUID | str, charset: CharsetSpec
) -> None:
    sidecar = TemplateSidecar(layout.pages, str(template_id), charset.charset_id, charset.version)
    validate_sidecar(sidecar, charset)
    payload = asdict(sidecar)
    # Padding is represented by absent mappings in the interchange format.
    for page in payload["pages"]:
        page["cells"] = [cell for cell in page["cells"] if cell["codepoint"] is not None]

    def rounded(value: Any) -> Any:
        if isinstance(value, float):
            return round(value, 2)
        if isinstance(value, dict):
            return {k: rounded(v) for k, v in value.items()}
        if isinstance(value, (list, tuple)):
            return [rounded(v) for v in value]
        return value

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(rounded(payload), sort_keys=True, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def read_sidecar(path: Path, expected_charset: CharsetSpec | None = None) -> TemplateSidecar:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        pages = tuple(
            TemplatePage(
                index=p["index"],
                aruco_ids=tuple(p["aruco_ids"]),
                content_mm=ContentGeometry(**p["content_mm"]),
                grid_mm=GridGeometry(**p["grid_mm"]),
                cells=tuple(Cell(**c) for c in p["cells"]),
            )
            for p in data["pages"]
        )
        result = TemplateSidecar(
            pages,
            data["template_id"],
            data["charset_id"],
            data["charset_version"],
            data["schema"],
        )
        validate_sidecar(result, expected_charset)
        return result
    except GlyphlabError:
        raise
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
        raise GlyphlabError("E_TEMPLATE_MISMATCH", "Invalid template sidecar") from exc

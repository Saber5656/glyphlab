"""Pure A4 geometry. Persisted page geometry remains authoritative for old sheets."""

from dataclasses import dataclass
from math import ceil, floor
from typing import Literal

from glyphlab.charset import CharsetSpec
from glyphlab.errors import GlyphlabError

MM_TO_PX = 300 / 25.4
PAGE_MM = (210.0, 297.0)
RASTER_SIZE = (2481, 3508)
MARGIN_MM = 12.0
MARKER_MM = 14.0
COLS = ROWS = 7
CELL_MM = 25.0
LABEL_MM = 3.0
GAP_MM = 1.5
INSET_MM = 2.0
ScriptClass = Literal["latin", "kana", "punct_ja"]


@dataclass(frozen=True)
class GuideGeometry:
    baseline: float | None = None
    xheight: float | None = None
    square: tuple[float, float, float, float] | None = None


def guide_geometry(box: tuple[float, float, float, float], script_class: str) -> GuideGeometry:
    x0, y0, x1, y1 = box
    w, h = x1 - x0, y1 - y0
    if script_class == "latin":
        return GuideGeometry(baseline=y1 - 0.30 * h, xheight=y1 - 0.62 * h)
    return GuideGeometry(square=(x0 + 0.06 * w, y0 + 0.06 * h, x1 - 0.06 * w, y1 - 0.06 * h))


@dataclass(frozen=True)
class ContentGeometry:
    x0: float = 12.0
    y0: float = 36.0
    x1: float = 198.0
    y1: float = 283.0
    marker: float = MARKER_MM


@dataclass(frozen=True)
class GridGeometry:
    x0: float = 12.0
    y0: float = 54.0
    cell: float = CELL_MM
    label_h: float = LABEL_MM
    gap: float = GAP_MM
    cols: int = COLS
    rows: int = ROWS


@dataclass(frozen=True)
class Cell:
    row: int
    col: int
    codepoint: int | None


@dataclass(frozen=True)
class TemplatePage:
    index: int
    aruco_ids: tuple[int, ...]
    content_mm: ContentGeometry
    grid_mm: GridGeometry
    cells: tuple[Cell, ...]

    def cells_with_chars(self) -> list[Cell]:
        return [c for c in self.cells if c.codepoint is not None]

    def writing_box_mm(self, row: int, col: int) -> tuple[float, float, float, float]:
        g = self.grid_mm
        x = g.x0 + col * (g.cell + g.gap)
        y = g.y0 + row * (g.cell + g.label_h + g.gap) + g.label_h
        return (x, y, x + g.cell, y + g.cell)

    def marker_rects_mm(self) -> tuple[tuple[float, float, float, float], ...]:
        c = self.content_mm
        return (
            (c.x0, c.y0, c.x0 + c.marker, c.y0 + c.marker),
            (c.x1 - c.marker, c.y0, c.x1, c.y0 + c.marker),
            (c.x1 - c.marker, c.y1 - c.marker, c.x1, c.y1),
            (c.x0, c.y1 - c.marker, c.x0 + c.marker, c.y1),
        )

    def content_corners_px(self) -> tuple[tuple[float, float], ...]:
        c = self.content_mm
        return tuple(
            (x * MM_TO_PX, y * MM_TO_PX)
            for x, y in ((c.x0, c.y0), (c.x1, c.y0), (c.x1, c.y1), (c.x0, c.y1))
        )


@dataclass(frozen=True)
class TemplateLayout:
    pages: tuple[TemplatePage, ...]

    @property
    def page_count(self) -> int:
        return len(self.pages)


def compute_layout(charset: CharsetSpec) -> TemplateLayout:
    chars = charset.drawn_chars()
    count = ceil(len(chars) / (COLS * ROWS))
    if not 1 <= count <= 12:
        raise GlyphlabError("E_VALIDATION", "Template must contain between 1 and 12 pages")
    pages = []
    for k in range(count):
        cells = tuple(
            Cell(
                i // COLS,
                i % COLS,
                chars[k * 49 + i].codepoint if k * 49 + i < len(chars) else None,
            )
            for i in range(49)
        )
        pages.append(
            TemplatePage(
                k,
                tuple(range(4 * k, 4 * k + 4)),
                ContentGeometry(),
                GridGeometry(),
                cells,
            )
        )
    return TemplateLayout(tuple(pages))


def marker_rect_mm(page: TemplatePage, which: int) -> tuple[float, float, float, float]:
    return page.marker_rects_mm()[which]


def cell_box_px(page: TemplatePage, row: int, col: int) -> tuple[int, int, int, int]:
    x0, y0, x1, y1 = page.writing_box_mm(row, col)
    return (
        floor((x0 + INSET_MM) * MM_TO_PX),
        floor((y0 + INSET_MM) * MM_TO_PX),
        ceil((x1 - INSET_MM) * MM_TO_PX),
        ceil((y1 - INSET_MM) * MM_TO_PX),
    )


def guide_lines_px(page: TemplatePage, cell: Cell, script_class: str) -> GuideGeometry:
    crop = cell_box_px(page, cell.row, cell.col)
    x0, y0, x1, y1 = page.writing_box_mm(cell.row, cell.col)
    return guide_geometry(
        (
            x0 * MM_TO_PX - crop[0],
            y0 * MM_TO_PX - crop[1],
            x1 * MM_TO_PX - crop[0],
            y1 * MM_TO_PX - crop[1],
        ),
        script_class,
    )

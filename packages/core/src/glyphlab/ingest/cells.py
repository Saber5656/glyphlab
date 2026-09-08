"""Cell slicing, illumination normalization, and bounded ink classification."""

from collections.abc import Iterator
from dataclasses import dataclass

import cv2
import numpy as np

from glyphlab.model import GlyphWarning
from glyphlab.template.layout import GuideGeometry, cell_box_px, guide_lines_px
from glyphlab.template.sidecar import TemplateSidecar

from .rectify import RectifiedPage


@dataclass(frozen=True)
class CellGeometry:
    codepoint: int
    script_class: str
    cell_ref: tuple[int, int, int]
    box_px: tuple[int, int, int, int]
    guides: GuideGeometry


@dataclass(frozen=True)
class CellBitmap:
    geom: CellGeometry
    bitmap: np.ndarray
    ink_ratio: float
    warnings: list[GlyphWarning]
    failed: bool = False

    @property
    def is_empty(self) -> bool:
        return self.ink_ratio < 0.005


def slice_cells(
    page: RectifiedPage, sidecar: TemplateSidecar
) -> Iterator[tuple[CellGeometry, np.ndarray]]:
    layout = next(p for p in sidecar.pages if p.index == page.page_index)
    for cell in layout.cells:
        if cell.codepoint is None:
            continue
        cp = cell.codepoint
        # Custom charsets obey the same script-class rule as the charset module.
        script = (
            "latin"
            if cp < 128
            else (
                "kana"
                if 0x3041 <= cp <= 0x3096 or 0x30A1 <= cp <= 0x30FA or cp == 0x30FC
                else "punct_ja"
            )
        )
        box = cell_box_px(layout, cell.row, cell.col)
        x0, y0, x1, y1 = box
        geom = CellGeometry(
            cp,
            script,
            (page.page_index, cell.row, cell.col),
            box,
            guide_lines_px(layout, cell, script),
        )
        yield geom, page.canvas[y0:y1, x0:x1].copy()


def binarize_cell(cell: np.ndarray, geom: CellGeometry) -> CellBitmap:
    background = cv2.GaussianBlur(cell.astype(np.float32), (0, 0), max(cell.shape) / 4)
    flat = np.clip(cell.astype(np.float32) / np.maximum(background, 1) * 255, 0, 255).astype(
        np.uint8
    )
    threshold, binary = cv2.threshold(flat, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)
    # Otsu alone splits a blank sheet's two tones into paper and printed guides.
    # A relative darkness ceiling removes guides even in uniformly dark photos.
    binary[flat > min(threshold, 170)] = 0
    # Bound dense high-frequency input before morphology erases its evidence.
    transitions = np.count_nonzero(binary[:, 1:] != binary[:, :-1]) + np.count_nonzero(
        binary[1:, :] != binary[:-1, :]
    )
    hostile = transitions > binary.size * 0.8
    opened = cv2.morphologyEx(binary, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    _count, labels, stats, _ = cv2.connectedComponentsWithStats(opened, connectivity=8)
    keep = np.flatnonzero(stats[1:, cv2.CC_STAT_AREA] >= 9) + 1
    cleaned = np.isin(labels, keep)
    ratio = float(np.count_nonzero(cleaned) / cleaned.size)
    warnings = []
    if 0.005 <= ratio < 0.015:
        warnings.append(GlyphWarning.LOW_INK)
    if ratio > 0.4:
        warnings.append(GlyphWarning.LARGE_INK_BLOB)
    if cleaned[0].any() or cleaned[-1].any() or cleaned[:, 0].any() or cleaned[:, -1].any():
        warnings.append(GlyphWarning.TOUCHES_BORDER)
    return CellBitmap(geom, cleaned, ratio, warnings, bool(len(keep) > 64 or hostile))

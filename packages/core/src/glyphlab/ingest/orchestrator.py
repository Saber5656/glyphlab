"""Storage-agnostic scan pipeline and review-aware re-ingest policy."""

from collections import Counter
from dataclasses import dataclass, field
from typing import Any

from glyphlab.charset import CharsetSpec
from glyphlab.errors import GlyphlabError
from glyphlab.fit import fit_glyph
from glyphlab.model import GlyphStatus
from glyphlab.template.sidecar import TemplateSidecar, validate_sidecar
from glyphlab.vectorize import TraceOpts, VectorizerEngine

from .cells import binarize_cell, slice_cells
from .decode import decode_scan
from .rectify import detect_and_rectify
from .sinks import GlyphSink


@dataclass(frozen=True)
class CellIngestResult:
    codepoint: str
    outcome: str
    warnings: list[str] = field(default_factory=list)
    error_code: str | None = None

    def to_dict(self) -> dict[str, Any]:
        result = {
            "codepoint": self.codepoint,
            "outcome": self.outcome,
            "warnings": self.warnings,
        }
        if self.error_code:
            result["error_code"] = self.error_code
        return result


@dataclass(frozen=True)
class PageIngestResult:
    page_index: int
    template_id: str
    cells: list[CellIngestResult]
    diagnostics: dict[str, Any]
    schema: str = "glyphlab.ingest-report/1"

    @property
    def counts(self) -> dict[str, int]:
        counts = Counter(c.outcome for c in self.cells)
        return {k: counts[k] for k in ("extracted", "empty", "skipped_accepted", "failed")}

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "page_index": self.page_index,
            "template_id": self.template_id,
            "counts": self.counts,
            "cells": [c.to_dict() for c in self.cells],
            "diagnostics": self.diagnostics,
        }


def ingest_scan(
    data: bytes,
    *,
    sidecar: TemplateSidecar,
    charset: CharsetSpec,
    store: GlyphSink,
    engine: VectorizerEngine,
    force: bool = False,
) -> PageIngestResult:
    from glyphlab.project.glyph_svg import render_glyph_svg

    validate_sidecar(sidecar, charset)
    page = detect_and_rectify(decode_scan(data), sidecar)
    chars = {char.codepoint: char for char in charset.chars}
    outcomes = []
    for geom, crop in slice_cells(page, sidecar):
        cell = binarize_cell(crop, geom)
        cp = f"U+{geom.codepoint:04X}"
        warnings = [str(w) for w in cell.warnings]
        if cell.failed:
            outcomes.append(CellIngestResult(cp, "failed", warnings, "E_VALIDATION"))
        elif cell.is_empty:
            outcomes.append(CellIngestResult(cp, "empty", warnings))
        elif store.get_status(geom.codepoint) == GlyphStatus.ACCEPTED and not force:
            outcomes.append(CellIngestResult(cp, "skipped_accepted", warnings))
        else:
            try:
                contours = engine.trace(cell.bitmap, TraceOpts())
                glyph = fit_glyph(contours, geom, chars[geom.codepoint], cell.warnings)
                svg = render_glyph_svg(glyph)
                store.put_glyph(glyph, svg)
                outcomes.append(CellIngestResult(cp, "extracted", [str(w) for w in glyph.warnings]))
            except GlyphlabError as exc:
                outcomes.append(CellIngestResult(cp, "failed", warnings, exc.code))
    return PageIngestResult(
        page.page_index,
        sidecar.template_id,
        sorted(outcomes, key=lambda c: int(c.codepoint[2:], 16)),
        page.diagnostics,
    )

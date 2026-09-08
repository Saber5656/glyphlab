"""Storage seam shared by local CLI and hosted ingest workers."""

from typing import Protocol

from glyphlab.model import Glyph, GlyphStatus
from glyphlab.project.store import ProjectStore


class GlyphSink(Protocol):
    def get_status(self, cp: int) -> GlyphStatus: ...
    def put_glyph(self, glyph: Glyph, svg_bytes: bytes) -> None: ...


class ProjectGlyphSink:
    def __init__(self, store: ProjectStore) -> None:
        self.store = store

    def get_status(self, cp: int) -> GlyphStatus:
        record = self.store.get_status(cp)
        if isinstance(record, dict):
            return GlyphStatus(record.get("status", "missing"))
        return GlyphStatus.MISSING

    def put_glyph(self, glyph: Glyph, svg_bytes: bytes) -> None:
        self.store.put_glyph(glyph, svg_bytes)

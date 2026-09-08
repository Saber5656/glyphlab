"""Select paths from review state; the restricted parser is the next trust boundary."""

from pathlib import Path

from glyphlab.project.store import ProjectStore


def collect_buildable_glyphs(store: ProjectStore, include_unreviewed: bool) -> dict[int, Path]:
    states = {"accepted", "auto"} if include_unreviewed else {"accepted"}
    return {
        int(key[2:], 16): store.glyph_svg_path(int(key[2:], 16))
        for key, entry in store.read_status().items()
        if entry["status"] in states
    }

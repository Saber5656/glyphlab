from pathlib import Path

from glyphlab.charset.model import CharDef, CharsetSpec
from glyphlab.fontbuild.builder import build_font
from glyphlab.model import Contour, CubicSegment, GlyphOutline, Point
from glyphlab.project.config import ProjectConfig


def box(x0=100, y0=0, x1=700, y1=700):
    points = [Point(x0, y0), Point(x1, y0), Point(x1, y1), Point(x0, y1), Point(x0, y0)]
    return GlyphOutline(
        (
            Contour(
                tuple(CubicSegment(a, a, b, b) for a, b in zip(points, points[1:], strict=False))
            ),
        )
    )


def make_golden_inputs():
    chars = tuple(
        CharDef(cp, script, drawn)
        for cp, script, drawn in [
            (32, "latin", False),
            (46, "latin", True),
            (65, "latin", True),
            (0x3000, "punct_ja", False),
            (0x3002, "punct_ja", True),
            (0x3042, "kana", True),
            (0x30A2, "kana", True),
        ]
    )
    charset = CharsetSpec("golden", 1, chars)
    config = ProjectConfig.model_validate(
        {
            "project": {
                "name": "Golden",
                "family_name": "Golden Hand",
                "charset": "ascii",
                "version": 1,
            }
        }
    )
    glyphs = {
        c.codepoint: (
            box(x1=450 if c.script_class == "latin" else 800),
            600 if c.script_class == "latin" else 1000,
        )
        for c in chars
        if c.drawn
    }
    return config, glyphs, charset


def make_golden_font(tmp_path: Path, golden_inputs):
    return build_font(*golden_inputs, tmp_path)

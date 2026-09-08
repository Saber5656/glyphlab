from pathlib import Path

import pytest
from glyphlab.errors import GlyphSvgInvalidError
from glyphlab.model import Contour, CubicSegment, GlyphOutline, Point
from glyphlab.project.glyph_svg import read_glyph_svg, write_glyph_svg

PREFIX = '<svg xmlns="x" viewBox="0 -880 1000 1000" data-glyphlab="glyph/1" '


def _svg(body: str) -> str:
    return PREFIX + 'data-codepoint="U+0041" data-advance="1000">' + body + "</svg>"


def outline() -> GlyphOutline:
    p = Point
    return GlyphOutline(
        (
            Contour(
                (
                    CubicSegment(p(0, 0), p(1, 2), p(3, 4), p(5, 6)),
                    CubicSegment(p(5, 6), p(7, 8), p(9, 10), p(0, 0)),
                )
            ),
        )
    )


def test_svg_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "glyph.svg"
    write_glyph_svg(path, outline(), 0x3042, 1000)
    parsed, advance = read_glyph_svg(path)
    assert advance == 1000
    assert parsed == outline()
    assert 'data-codepoint="U+3042"' in path.read_text()


@pytest.mark.parametrize(
    "content",
    [
        "<!DOCTYPE svg>" + _svg('<path d="M 0 0 Z"/>'),
        _svg("<script/>"),
        _svg('<path transform="scale(2)" d="M 0 0 Z"/>'),
        _svg('<path d="m 0 0 Z"/>'),
        _svg('<path fill="url(x)" d="M 0 0 Z"/>'),
    ],
)
def test_rejects_malformed_svg(tmp_path: Path, content: str) -> None:
    path = tmp_path / "bad.svg"
    path.write_text(content)
    with pytest.raises(GlyphSvgInvalidError) as raised:
        read_glyph_svg(path)
    assert raised.value.code == "E_GLYPH_SVG_INVALID"
    assert str(raised.value)


def test_named_malformed_fixtures() -> None:
    malformed = Path(__file__).parent / "malformed"
    fixtures = sorted(malformed.glob("*.svg"))
    assert [fixture.name for fixture in fixtures] == [
        f"{index:02d}-{name}.svg"
        for index, name in enumerate(
            [
                "doctype",
                "entity",
                "script-element",
                "image-href",
                "transform-attr",
                "two-paths",
                "relative-commands",
                "fill-url",
                "bad-viewbox",
                "oversize-256k",
            ],
            1,
        )
    ]
    for fixture in fixtures:
        with pytest.raises(GlyphSvgInvalidError):
            read_glyph_svg(fixture)

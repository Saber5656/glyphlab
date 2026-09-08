import pytest
from fontTools.ttLib import TTFont
from glyphlab.qa.model import ExpectedBuild
from glyphlab.qa.structural import run_structural_checks


def expected_for(charset, glyphs):
    return ExpectedBuild(
        {c.codepoint for c in charset.chars},
        {**{cp: a for cp, (_, a) in glyphs.items()}, 32: 500, 0x3000: 1000},
    )


def test_valid(golden_font, golden_inputs):
    _, glyphs, charset = golden_inputs
    assert run_structural_checks(golden_font.ttf_path, charset, expected_for(charset, glyphs)) == []


@pytest.mark.parametrize(
    "mutation,check",
    [
        ("cmap", "structural/cmap"),
        ("advance", "structural/advance"),
        ("floor", "structural/advance"),
        ("empty", "structural/outline"),
        ("bounds", "structural/bounds"),
        ("metrics", "structural/metrics"),
    ],
)
def test_corruption(golden_font, golden_inputs, mutation, check):
    _, glyphs, charset = golden_inputs
    path = golden_font.ttf_path
    font = TTFont(path)
    name = font.getBestCmap()[0x3042]
    if mutation == "cmap":
        for subtable in font["cmap"].tables:
            subtable.cmap.pop(0x3042, None)
    elif mutation in ("advance", "floor"):
        font["hmtx"][name] = (999 if mutation == "advance" else 100, 0)
    elif mutation == "empty":
        font["glyf"][name].numberOfContours = 0
    elif mutation == "bounds":
        font["glyf"][name].coordinates[0] = (2500, 0)
    else:
        font["OS/2"].usWinAscent = 500
    font.save(path)
    assert check in {
        f.check_id for f in run_structural_checks(path, charset, expected_for(charset, glyphs))
    }


def test_format_12_must_match_coverage(golden_font, golden_inputs):
    _, glyphs, charset = golden_inputs
    font = TTFont(golden_font.ttf_path)
    next(t for t in font["cmap"].tables if t.format == 12).cmap.pop(65)
    font.save(golden_font.ttf_path)
    assert any(
        f.check_id == "structural/cmap"
        for f in run_structural_checks(golden_font.ttf_path, charset, expected_for(charset, glyphs))
    )


def test_supplementary_custom_codepoint_uses_format_12(golden_inputs, tmp_path):
    from glyphlab.charset.model import CharDef, CharsetSpec
    from glyphlab.fontbuild.builder import build_font

    config, glyphs, _ = golden_inputs
    charset = CharsetSpec(
        "supplementary", 1, (CharDef(32, "latin", False), CharDef(0x1F600, "latin", True))
    )
    result = build_font(config, {0x1F600: glyphs[65]}, charset, tmp_path)
    findings = run_structural_checks(
        result.ttf_path, charset, ExpectedBuild({32, 0x1F600}, {32: 500, 0x1F600: 600})
    )
    assert findings == []

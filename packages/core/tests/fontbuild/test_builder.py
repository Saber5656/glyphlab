import pytest
from fontTools.ttLib import TTFont
from glyphlab.errors import GlyphlabError
from glyphlab.fontbuild.builder import build_font


def test_required_tables_and_names(golden_font, golden_inputs):
    config, glyphs, charset = golden_inputs
    with TTFont(golden_font.ttf_path, lazy=False) as font:
        for key in font.keys():
            font[key]
        cmap = font.getBestCmap()
        assert set(cmap) == {c.codepoint for c in charset.chars}
        assert font.getGlyphOrder()[0] == ".notdef"
        assert {t.format for t in font["cmap"].tables} >= {4, 12}
        assert font["head"].unitsPerEm == 1000
        assert font["head"].lowestRecPPEM == 7
        assert font["hhea"].ascent == 880
        assert font["hhea"].descent == -120
        assert font["hhea"].lineGap == 0
        assert font["OS/2"].sTypoAscender == 880
        assert font["OS/2"].sTypoDescender == -120
        assert font["OS/2"].usWinAscent == 880
        assert font["OS/2"].usWinDescent == 120
        assert font["OS/2"].fsType == 0
        assert font["OS/2"].ulCodePageRange1 == (1 | 1 << 17)
        assert font["post"].formatType == 2
        assert font["gasp"].gaspRange == {65535: 15}
        assert font["name"].getDebugName(1) == "Golden Hand"
        assert font["name"].getDebugName(3) == "glyphlab:Golden Hand:1"
        assert font["name"].getDebugName(5) == "Version 1.000"
        assert font["name"].getDebugName(6) == "GoldenHand-Regular"
        assert font["hmtx"][cmap[32]][0] == 500
        assert font["hmtx"][cmap[0x3000]][0] == 1000
        assert font["hmtx"][cmap[0x3042]][0] == 1000
    with TTFont(golden_font.woff2_path) as webfont:
        assert len(webfont.getGlyphOrder()) == len(charset.chars) + 1
    assert golden_font.missing == []


def test_missing_and_unknown(golden_inputs, tmp_path):
    config, glyphs, charset = golden_inputs
    del glyphs[65]
    assert build_font(config, glyphs, charset, tmp_path).missing == ["U+0041"]
    glyphs[66] = glyphs[46]
    with pytest.raises(GlyphlabError) as error:
        build_font(config, glyphs, charset, tmp_path)
    assert error.value.code == "E_VALIDATION"

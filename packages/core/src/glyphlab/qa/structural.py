"""Mandatory checks for generated font integrity; never bypassed by --skip-bakery."""

from pathlib import Path

from fontTools.ttLib import TTFont

from glyphlab.charset.model import CharsetSpec
from glyphlab.qa.model import ExpectedBuild, QAFinding


def run_structural_checks(
    ttf_path: Path,
    charset: CharsetSpec,
    expected: ExpectedBuild,
) -> list[QAFinding]:
    findings: list[QAFinding] = []

    def fail(check: str, message: str) -> None:
        findings.append(QAFinding(f"structural/{check}", "FAIL", message))

    try:
        with TTFont(ttf_path, lazy=False) as font:
            for key in font.keys():
                font[key]
            cmap = font.getBestCmap() or {}
            if set(cmap) != expected.codepoints:
                fail("cmap", "Character map differs from the selected charset coverage")
            definitions = {c.codepoint: c for c in charset.chars}
            for cp, name in cmap.items():
                advance = font["hmtx"][name][0]
                char = definitions.get(cp)
                target = expected.advances.get(cp)
                if cp == 32:
                    target = 500
                elif cp == 0x3000 or (char and char.script_class in ("kana", "punct_ja")):
                    target = 1000
                if advance < 120 or (target is not None and advance != target):
                    fail("advance", f"U+{cp:04X}: invalid advance {advance}; expected {target}")
                glyph = font["glyf"][name]
                if char and char.drawn and glyph.numberOfContours == 0:
                    fail("outline", f"U+{cp:04X}: drawn glyph has no outline")
                coords, _, _ = glyph.getCoordinates(font["glyf"])
                if any(not (-200 <= x <= 2000 and -250 <= y <= 1000) for x, y in coords):
                    fail("bounds", f"U+{cp:04X}: outline exceeds allowed bounds")
            codepages = 1 | (
                1 << 17 if any(c.script_class != "latin" for c in charset.chars) else 0
            )
            required = {
                "head": {"unitsPerEm": 1000, "lowestRecPPEM": 7},
                "hhea": {"ascent": 880, "descent": -120, "lineGap": 0},
                "OS/2": {
                    "sTypoAscender": 880,
                    "sTypoDescender": -120,
                    "sTypoLineGap": 0,
                    "usWinAscent": 880,
                    "usWinDescent": 120,
                    "fsType": 0,
                    "ulCodePageRange1": codepages,
                },
            }
            for table, fields in required.items():
                for field, value in fields.items():
                    if getattr(font[table], field) != value:
                        fail("metrics", f"{table}.{field} must be {value}")
    except Exception as exc:
        fail("font", f"Unable to load complete font: {exc}")
    return findings

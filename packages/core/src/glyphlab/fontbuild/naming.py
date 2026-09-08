"""Deterministic, user-owned font metadata."""

from fontTools.agl import UV2AGL


def glyph_name(codepoint: int) -> str:
    return str(UV2AGL.get(codepoint, f"uni{codepoint:04X}"))


def name_table(family_name: str, version: int, year: int) -> dict[int, str]:
    url = "https://github.com/Saber5656/glyphlab"
    return {
        0: f"Copyright {year} the font author. Generated with glyphlab.",
        1: family_name,
        2: "Regular",
        3: f"glyphlab:{family_name}:{version}",
        4: f"{family_name} Regular",
        5: f"Version {version}.000",
        6: f"{family_name.replace(' ', '')}-Regular",
        11: url,
        13: "The font and the handwriting it embodies belong to the person who wrote it. "
        "glyphlab claims no rights over generated fonts.",
        14: url,
    }

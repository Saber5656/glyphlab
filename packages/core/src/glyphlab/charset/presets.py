"""Built-in, immutable charset presets."""

from glyphlab.charset.model import CharDef, CharsetSpec, ScriptClass


class UnknownCharsetError(ValueError):
    """Raised when a requested preset does not exist."""


def _range(start: int, end: int, script_class: ScriptClass) -> list[CharDef]:
    return [CharDef(cp, script_class, True) for cp in range(start, end + 1)]


def _make_ascii() -> CharsetSpec:
    return CharsetSpec(
        "ascii",
        1,
        tuple([CharDef(0x20, "latin", False), *_range(0x21, 0x7E, "latin")]),
    )


def _make_kana() -> CharsetSpec:
    chars = [
        CharDef(0x3000, "punct_ja", False),
        *[CharDef(cp, "punct_ja", True) for cp in (0x3001, 0x3002, 0x300C, 0x300D)],
        *_range(0x3041, 0x3096, "kana"),
        *_range(0x30A1, 0x30FA, "kana"),
        CharDef(0x30FB, "punct_ja", True),
        CharDef(0x30FC, "kana", True),
    ]
    return CharsetSpec("kana", 1, tuple(sorted(chars, key=lambda char: char.codepoint)))


ASCII = _make_ascii()
KANA = _make_kana()
JA_BASIC_V1 = CharsetSpec(
    "ja-basic-v1", 1, tuple(sorted(ASCII.chars + KANA.chars, key=lambda c: c.codepoint))
)
PRESETS: dict[str, CharsetSpec] = {spec.charset_id: spec for spec in (ASCII, KANA, JA_BASIC_V1)}
SYNTHESIZED_ADVANCES: dict[int, int] = {0x0020: 500, 0x3000: 1000}


def get_preset(charset_id: str) -> CharsetSpec:
    try:
        return PRESETS[charset_id]
    except KeyError as exc:
        raise UnknownCharsetError(f"unknown charset preset: {charset_id}") from exc

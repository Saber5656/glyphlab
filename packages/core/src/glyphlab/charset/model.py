"""Immutable charset domain types."""

from dataclasses import dataclass
from typing import Literal

ScriptClass = Literal["latin", "kana", "punct_ja"]


@dataclass(frozen=True)
class CharDef:
    codepoint: int
    script_class: ScriptClass
    drawn: bool


@dataclass(frozen=True)
class CharsetSpec:
    charset_id: str
    version: int
    chars: tuple[CharDef, ...]

    def __post_init__(self) -> None:
        codepoints = tuple(char.codepoint for char in self.chars)
        if codepoints != tuple(sorted(codepoints)) or len(set(codepoints)) != len(codepoints):
            raise ValueError("charset codepoints must be strictly ascending and unique")
        if any(cp < 0 or cp > 0x10FFFF or 0xD800 <= cp <= 0xDFFF for cp in codepoints):
            raise ValueError("charset contains an invalid Unicode scalar value")
        if self.version < 1:
            raise ValueError("charset version must be at least 1")

    def codepoints(self) -> tuple[int, ...]:
        return tuple(char.codepoint for char in self.chars)

    def drawn_chars(self) -> tuple[CharDef, ...]:
        return tuple(char for char in self.chars if char.drawn)

    def get(self, codepoint: int) -> CharDef | None:
        return next((char for char in self.chars if char.codepoint == codepoint), None)

    def __len__(self) -> int:
        return len(self.chars)

    def __contains__(self, codepoint: object) -> bool:
        return isinstance(codepoint, int) and any(
            char.codepoint == codepoint for char in self.chars
        )

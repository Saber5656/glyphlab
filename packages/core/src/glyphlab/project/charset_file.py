"""Secure parser for CLI-only custom charset TOML files."""

import re
import tomllib
from pathlib import Path

from glyphlab.charset import CharDef, CharsetSpec, ScriptClass
from glyphlab.errors import ConfigError

_CODEPOINT = re.compile(r"^U\+([0-9A-Fa-f]{4,6})$")


def _parse_codepoint(value: str) -> int:
    if len(value) == 1:
        return ord(value)
    match = _CODEPOINT.fullmatch(value)
    if match is None:
        raise ConfigError(f"invalid custom charset character: {value}")
    codepoint = int(match.group(1), 16)
    if codepoint > 0x10FFFF or 0xD800 <= codepoint <= 0xDFFF:
        raise ConfigError(f"invalid Unicode scalar value: {value}")
    return codepoint


def _script_class(codepoint: int) -> ScriptClass:
    if 0x3040 <= codepoint <= 0x309F or 0x30A0 <= codepoint <= 0x30FF:
        return "kana"
    if 0x3000 <= codepoint <= 0x303F:
        return "punct_ja"
    return "latin"


def load_custom_charset(path: Path) -> CharsetSpec:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise ConfigError(f"could not read custom charset: {exc}") from exc
    if len(raw) > 4096:
        raise ConfigError("custom charset exceeds 4096 bytes")
    try:
        data = tomllib.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, tomllib.TOMLDecodeError) as exc:
        raise ConfigError(f"invalid custom charset TOML: {exc}") from exc
    if not isinstance(data.get("name"), str) or not isinstance(data.get("version"), int):
        raise ConfigError("custom charset requires name and integer version")
    entries = data.get("chars")
    if not isinstance(entries, list) or not all(isinstance(entry, str) for entry in entries):
        raise ConfigError("custom charset chars must be a list of strings")
    points: set[int] = set()
    for entry in entries:
        if "-" in entry and entry.startswith("U+"):
            start_text, end_text = entry.split("-", 1)
            start = _parse_codepoint(start_text)
            end = _parse_codepoint(end_text)
            if end < start:
                raise ConfigError(f"custom charset range is descending: {entry}")
            points.update(range(start, end + 1))
        else:
            points.add(_parse_codepoint(entry))
    drawn_count = sum(point not in (0x0020, 0x3000) for point in points)
    if drawn_count > 500:
        raise ConfigError("custom charset exceeds 500 drawn characters")
    chars = tuple(
        CharDef(point, _script_class(point), point not in (0x0020, 0x3000))
        for point in sorted(points)
    )
    try:
        return CharsetSpec(data["name"], data["version"], chars)
    except ValueError as exc:
        raise ConfigError(str(exc)) from exc

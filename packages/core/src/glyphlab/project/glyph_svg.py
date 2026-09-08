"""Canonical glyph SVG writer and restricted, hardened parser."""

import html
import re
from pathlib import Path

from defusedxml import ElementTree as ET

from glyphlab.errors import GlyphSvgInvalidError
from glyphlab.model import Contour, CubicSegment, Glyph, GlyphOutline, Point

_NUMBER = r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)"
_TOKEN = re.compile(rf"(?P<command>[A-Za-z])|(?P<number>{_NUMBER})")
_CODEPOINT = re.compile(r"^U\+[0-9A-F]{4,6}$")
_ROOT_ATTRIBUTES = {"viewBox", "data-glyphlab", "data-codepoint", "data-advance"}


def _fmt(value: float) -> str:
    if abs(value) < 0.005:
        value = 0.0
    return f"{value:.2f}"


def _render_glyph_svg(outline: GlyphOutline, codepoint: int, advance: int) -> bytes:
    if not 120 <= advance <= 2000:
        raise ValueError("advance must be between 120 and 2000")
    if codepoint < 0 or codepoint > 0x10FFFF or 0xD800 <= codepoint <= 0xDFFF:
        raise ValueError("invalid Unicode codepoint")
    chunks: list[str] = []
    for contour in outline.contours:
        first = contour.segments[0].p1
        chunks.append(f"M {_fmt(first.x)} {_fmt(-first.y)}")
        for segment in contour.segments:
            if segment.c1 == segment.p1 and segment.c2 == segment.p2:
                chunks.append(f"L {_fmt(segment.p2.x)} {_fmt(-segment.p2.y)}")
            else:
                chunks.append(
                    "C "
                    + " ".join(
                        _fmt(value)
                        for point in (segment.c1, segment.c2, segment.p2)
                        for value in (point.x, -point.y)
                    )
                )
        chunks.append("Z")
    d = " ".join(chunks)
    content = (
        '<svg xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="0 -880 {advance} 1000" data-glyphlab="glyph/1" '
        f'data-codepoint="U+{codepoint:04X}" data-advance="{advance}">'
        f'<path d="{html.escape(d, quote=True)}" fill="black"/></svg>\n'
    )
    return content.encode("utf-8")


def write_glyph_svg(path: Path, outline: GlyphOutline, codepoint: int, advance: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_render_glyph_svg(outline, codepoint, advance))


def render_glyph_svg(glyph: Glyph) -> bytes:
    if glyph.outline is None or glyph.advance is None:
        raise ValueError("glyph must have an outline and advance")
    return _render_glyph_svg(glyph.outline, glyph.codepoint, glyph.advance)


def _invalid(reason: str) -> GlyphSvgInvalidError:
    return GlyphSvgInvalidError(f"invalid glyph SVG: {reason}", detail={"reason": reason})


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _parse_path(data: str) -> GlyphOutline:
    tokens: list[str | float] = []
    position = 0
    for match in _TOKEN.finditer(data):
        if data[position : match.start()].strip(" ,\t\r\n"):
            raise _invalid(f"offending token {data[position : match.start()].strip()!r}")
        tokens.append(match.group("command") or float(match.group("number")))
        position = match.end()
    if data[position:].strip(" ,\t\r\n"):
        raise _invalid(f"offending token {data[position:].strip()!r}")
    if not tokens:
        raise _invalid("empty path")
    index = 0
    contours: list[Contour] = []
    segments: list[CubicSegment] = []
    total_segments = 0
    current: Point | None = None
    start: Point | None = None
    closed = False
    counts = {"M": 2, "L": 2, "C": 6, "Z": 0}
    while index < len(tokens):
        command = tokens[index]
        if not isinstance(command, str):
            raise _invalid("path arguments must follow a command")
        if command not in counts:
            raise _invalid(f"offending token {command!r}; only M/L/C/Z are allowed")
        if command.islower():
            raise _invalid(f"offending token {command!r}; relative commands are forbidden")
        if command == "M":
            if not closed and current is not None:
                raise _invalid("new contour before Z")
            if index + 2 >= len(tokens) or not all(
                isinstance(item, float) for item in tokens[index + 1 : index + 3]
            ):
                raise _invalid("M requires two coordinates")
            x, y = tokens[index + 1 : index + 3]
            current = Point(float(x), -float(y))
            start = current
            segments = []
            closed = False
            index += 3
            continue
        if current is None or start is None or closed:
            raise _invalid(f"{command} appears outside a contour")
        arity = counts[command]
        values = tokens[index + 1 : index + 1 + arity]
        if len(values) != arity or not all(isinstance(item, float) for item in values):
            raise _invalid(f"{command} requires {arity} coordinates")
        points = [float(value) for value in values]
        if command == "L":
            endpoint = Point(points[0], -points[1])
            segments.append(CubicSegment(current, current, endpoint, endpoint))
            total_segments += 1
            current = endpoint
        elif command == "C":
            c1 = Point(points[0], -points[1])
            c2 = Point(points[2], -points[3])
            endpoint = Point(points[4], -points[5])
            segments.append(CubicSegment(current, c1, c2, endpoint))
            total_segments += 1
            current = endpoint
        else:
            if current != start:
                segments.append(CubicSegment(current, current, start, start))
                total_segments += 1
            if not segments:
                raise _invalid("contour has no drawable segments")
            contours.append(Contour(tuple(segments)))
            if len(contours) > 64:
                raise _invalid("maximum contour count is 64")
            closed = True
        if total_segments > 4000:
            raise _invalid("maximum segment count is 4000")
        index += 1 + arity
    if not closed:
        raise _invalid("path must end with Z")
    for contour in contours:
        for segment in contour.segments:
            for point in (segment.p1, segment.c1, segment.c2, segment.p2):
                if abs(point.x) > 4000 or abs(point.y) > 4000:
                    raise _invalid("coordinate exceeds ±4000 font units")
    return GlyphOutline(tuple(contours))


def read_glyph_svg(path: Path) -> tuple[GlyphOutline, int]:
    try:
        with path.open("rb") as handle:
            raw = handle.read(256 * 1024 + 1)
    except OSError as exc:
        raise _invalid(str(exc)) from exc
    if len(raw) > 256 * 1024:
        raise _invalid("document exceeds 256 KiB")
    try:
        text = raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise _invalid(f"UTF-8 decode failed: {exc}") from exc
    upper = text.upper()
    if "<!DOCTYPE" in upper or "<!ENTITY" in upper or "<?" in text:
        raise _invalid("DOCTYPE, entity declarations, and processing instructions are forbidden")
    try:
        root = ET.fromstring(raw)
    except (ET.ParseError, UnicodeDecodeError) as exc:
        raise _invalid(f"XML parse failed: {exc}") from exc
    if _local(root.tag) != "svg":
        raise _invalid("root element must be svg")
    attributes = {_local(key): value for key, value in root.attrib.items()}
    if set(attributes) != _ROOT_ATTRIBUTES:
        raise _invalid("root has unsupported or missing attributes")
    if attributes["data-glyphlab"] != "glyph/1":
        raise _invalid("data-glyphlab must equal glyph/1")
    if _CODEPOINT.fullmatch(attributes["data-codepoint"]) is None:
        raise _invalid("data-codepoint must use uppercase U+ notation")
    try:
        advance = int(attributes["data-advance"])
    except ValueError as exc:
        raise _invalid("data-advance must be an integer") from exc
    if not 120 <= advance <= 2000:
        raise _invalid("data-advance must be between 120 and 2000")
    if attributes["viewBox"] != f"0 -880 {advance} 1000":
        raise _invalid("viewBox does not match data-advance")
    children = list(root)
    if len(children) != 1 or _local(children[0].tag) != "path":
        raise _invalid("svg must contain exactly one path element")
    path_element = children[0]
    if list(path_element):
        raise _invalid("path must not contain child elements")
    child_attributes = {_local(key): value for key, value in path_element.attrib.items()}
    if set(child_attributes) - {"d", "fill"} or "d" not in child_attributes:
        raise _invalid("path has unsupported or missing attributes")
    if child_attributes.get("fill", "black") not in {"black", "#000", "#000000"}:
        raise _invalid("path fill must be black")
    return _parse_path(child_attributes["d"]), advance

"""Shared geometry and glyph domain models."""

from dataclasses import dataclass
from enum import StrEnum


@dataclass(frozen=True)
class Point:
    x: float
    y: float


@dataclass(frozen=True)
class CubicSegment:
    p1: Point
    c1: Point
    c2: Point
    p2: Point


@dataclass(frozen=True)
class Contour:
    segments: tuple[CubicSegment, ...]

    def __post_init__(self) -> None:
        if not self.segments:
            raise ValueError("a contour must contain at least one segment")
        if self.segments[0].p1 != self.segments[-1].p2:
            raise ValueError("a contour must be closed")

    @property
    def is_closed(self) -> bool:
        return bool(self.segments) and self.segments[0].p1 == self.segments[-1].p2


@dataclass(frozen=True)
class GlyphOutline:
    contours: tuple[Contour, ...]

    def bbox(self) -> tuple[float, float, float, float]:
        points = [
            point
            for contour in self.contours
            for segment in contour.segments
            for point in (segment.p1, segment.c1, segment.c2, segment.p2)
        ]
        if not points:
            return (0.0, 0.0, 0.0, 0.0)
        return (
            min(point.x for point in points),
            min(point.y for point in points),
            max(point.x for point in points),
            max(point.y for point in points),
        )

    def transform(self, scale: float, dx: float = 0.0, dy: float = 0.0) -> "GlyphOutline":
        def point(value: Point) -> Point:
            return Point(value.x * scale + dx, value.y * scale + dy)

        return GlyphOutline(
            tuple(
                Contour(
                    tuple(
                        CubicSegment(
                            point(segment.p1),
                            point(segment.c1),
                            point(segment.c2),
                            point(segment.p2),
                        )
                        for segment in contour.segments
                    )
                )
                for contour in self.contours
            )
        )


class GlyphStatus(StrEnum):
    MISSING = "missing"
    AUTO = "auto"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class GlyphWarning(StrEnum):
    LOW_INK = "LOW_INK"
    TOUCHES_BORDER = "TOUCHES_BORDER"
    TINY_CONTOURS_REMOVED = "TINY_CONTOURS_REMOVED"
    LARGE_INK_BLOB = "LARGE_INK_BLOB"
    OFF_GUIDE = "OFF_GUIDE"


@dataclass(frozen=True)
class GlyphSourceRef:
    upload: str
    cell: int


@dataclass
class Glyph:
    codepoint: int
    status: GlyphStatus
    outline: GlyphOutline | None
    advance: int | None
    warnings: list[GlyphWarning]
    source: GlyphSourceRef | None

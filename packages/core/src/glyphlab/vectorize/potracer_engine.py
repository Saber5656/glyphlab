from types import ModuleType

import numpy as np

from glyphlab.model import Contour, CubicSegment, Point

from .engine import TraceOpts, import_potracer, validate_bitmap
from .geometry import line_segment


class PotracerEngine:
    name = "potracer"

    def __init__(self, module: ModuleType | None = None):
        self.module = module if module is not None else import_potracer()

    def trace(self, bitmap: np.ndarray, opts: TraceOpts) -> list[Contour]:
        validate_bitmap(bitmap)
        path = self.module.Bitmap(~bitmap).trace(
            turdsize=opts.turdsize,
            alphamax=opts.alphamax,
            opttolerance=opts.opttolerance,
        )
        result = []
        for curve in path:
            current = Point(curve.start_point.x, curve.start_point.y)
            start = current
            segments: list[CubicSegment] = []
            for segment in curve:
                end = Point(segment.end_point.x, segment.end_point.y)
                if segment.is_corner:
                    corner = Point(segment.c.x, segment.c.y)
                    segments.extend((line_segment(current, corner), line_segment(corner, end)))
                else:
                    segments.append(
                        CubicSegment(
                            current,
                            Point(segment.c1.x, segment.c1.y),
                            Point(segment.c2.x, segment.c2.y),
                            end,
                        )
                    )
                current = end
            if current != start:
                segments.append(line_segment(current, start))
            if segments:
                result.append(Contour(tuple(segments)))
        return result

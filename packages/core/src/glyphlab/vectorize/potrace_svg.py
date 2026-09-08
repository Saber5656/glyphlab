"""Parse trusted potrace output separately from the restricted glyph SVG boundary."""

import re
from xml.etree import ElementTree as ET

from fontTools.pens.transformPen import TransformPen
from fontTools.svgLib.path import parse_path

from glyphlab.model import Contour

from .geometry import ContourPen


def parse_potrace_svg(data: bytes) -> list[Contour]:
    root = ET.fromstring(data)  # noqa: S314 -- local potrace process output only
    pen = ContourPen()
    for group in root.iter():
        if group.tag.rsplit("}", 1)[-1] != "g":
            continue
        transform = group.attrib.get("transform", "")
        translate = re.search(r"translate\(\s*([-+\d.eE]+)[ ,]+([-+\d.eE]+)\s*\)", transform)
        scale = re.search(r"scale\(\s*([-+\d.eE]+)[ ,]+([-+\d.eE]+)\s*\)", transform)
        tx, ty = map(float, translate.groups()) if translate else (0.0, 0.0)
        sx, sy = map(float, scale.groups()) if scale else (1.0, 1.0)
        transformed = TransformPen(pen, (sx, 0, 0, sy, tx, ty))
        for path in group:
            if path.tag.rsplit("}", 1)[-1] == "path":
                parse_path(path.attrib["d"], transformed)
    return pen.contours

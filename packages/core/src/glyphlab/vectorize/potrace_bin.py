import logging
import subprocess
from functools import lru_cache
from xml.etree.ElementTree import ParseError

import numpy as np
from defusedxml.common import DefusedXmlException

from glyphlab.errors import GlyphlabError
from glyphlab.model import Contour

from .engine import TraceOpts, validate_bitmap
from .potrace_svg import parse_potrace_svg


@lru_cache(maxsize=8)
def validate_executable(executable: str) -> None:
    try:
        result = subprocess.run(  # noqa: S603 -- trusted executable, fixed argv, no shell
            [executable, "--version"], capture_output=True, timeout=10, check=True
        )
        logging.getLogger(__name__).debug(
            "potrace version: %s",
            result.stdout.decode(errors="replace").splitlines()[0],
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise GlyphlabError("E_TRACE_UNAVAILABLE", "Unable to execute potrace") from exc


class PotraceBinaryEngine:
    name = "potrace"

    def __init__(self, executable: str):
        validate_executable(executable)
        self.executable = executable

    def trace(self, bitmap: np.ndarray, opts: TraceOpts) -> list[Contour]:
        validate_bitmap(bitmap)
        h, w = bitmap.shape
        pbm = f"P4\n{w} {h}\n".encode() + np.packbits(bitmap, axis=1).tobytes()
        argv = [
            self.executable,
            "--backend",
            "svg",
            "--turdsize",
            str(opts.turdsize),
            "--alphamax",
            str(opts.alphamax),
            "--opttolerance",
            str(opts.opttolerance),
            "--unit",
            "10",
            "-o",
            "-",
            "-",
        ]
        try:
            result = subprocess.run(  # noqa: S603 -- trusted executable, fixed argv, no shell
                argv, input=pbm, capture_output=True, timeout=10, check=False
            )
        except subprocess.TimeoutExpired as exc:
            raise GlyphlabError("E_TRACE_TIMEOUT", "Tracing exceeded ten seconds") from exc
        except OSError as exc:
            raise GlyphlabError("E_TRACE_UNAVAILABLE", "Unable to execute potrace") from exc
        if result.returncode:
            raise GlyphlabError(
                "E_INTERNAL",
                "Tracing process failed",
                detail={"stderr": result.stderr.decode(errors="replace")[:200]},
            )
        try:
            return parse_potrace_svg(result.stdout)
        except (ValueError, KeyError, ParseError, DefusedXmlException) as exc:
            raise GlyphlabError("E_INTERNAL", "Tracing returned malformed SVG") from exc

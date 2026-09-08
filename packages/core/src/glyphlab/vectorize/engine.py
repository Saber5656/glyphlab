import importlib
import os
import shutil
from collections.abc import Callable
from dataclasses import dataclass
from types import ModuleType
from typing import Literal, Protocol

import numpy as np

from glyphlab.errors import GlyphlabError
from glyphlab.model import Contour


@dataclass(frozen=True)
class TraceOpts:
    turdsize: int = 2
    alphamax: float = 1.0
    opttolerance: float = 0.2


class VectorizerEngine(Protocol):
    name: str

    def trace(self, bitmap: np.ndarray, opts: TraceOpts) -> list[Contour]: ...


def import_potracer() -> ModuleType:
    # PyPI distribution 'potracer' exposes the import package 'potrace'.
    return importlib.import_module("potrace")


def select_engine(
    pref: Literal["auto", "potrace", "potracer"] = "auto",
    *,
    _which: Callable[[str], str | None] = shutil.which,
    _import_potracer: Callable[[], ModuleType] = import_potracer,
) -> VectorizerEngine:
    from .potrace_bin import PotraceBinaryEngine
    from .potracer_engine import PotracerEngine

    if pref not in ("auto", "potrace", "potracer"):
        raise GlyphlabError("E_VALIDATION", "Unknown tracing engine")
    executable = _which(os.environ.get("GLYPHLAB_POTRACE_PATH", "potrace"))
    if executable and pref in ("auto", "potrace"):
        return PotraceBinaryEngine(executable)
    if pref in ("auto", "potracer"):
        try:
            return PotracerEngine(_import_potracer())
        except ImportError:
            pass
    raise GlyphlabError(
        "E_TRACE_UNAVAILABLE",
        "Install a tracing engine: brew install potrace or pip install 'glyphlab[trace]'",
    )


def validate_bitmap(bitmap: np.ndarray) -> None:
    if bitmap.ndim != 2 or bitmap.size > 1200 * 1200 or bitmap.dtype != np.bool_:
        raise GlyphlabError(
            "E_VALIDATION",
            "Trace bitmap must be boolean and at most 1200 squared pixels",
        )

"""Bounded image decode at the untrusted-byte boundary."""

import warnings
from io import BytesIO
from typing import Literal

import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError

from glyphlab.errors import GlyphlabError

Image.MAX_IMAGE_PIXELS = 36_000_000
try:
    from pillow_heif.as_plugin import register_heif_opener

    register_heif_opener()
    HEIC_AVAILABLE = True
except ImportError:
    HEIC_AVAILABLE = False


def sniff_format(head: bytes) -> Literal["jpeg", "png", "heic"] | None:
    if head.startswith(b"\xff\xd8\xff"):
        return "jpeg"
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if head[4:8] == b"ftyp" and head[8:12] in {b"heic", b"heix", b"mif1", b"msf1"}:
        return "heic"
    return None


def decode_scan(
    data: bytes, *, max_bytes: int = 12 * 2**20, max_pixels: int = 36_000_000
) -> np.ndarray:
    if len(data) > max_bytes:
        raise GlyphlabError("E_IMG_TOO_LARGE", "Image exceeds byte limit")
    fmt = sniff_format(data[:32])
    if fmt is None:
        raise GlyphlabError("E_IMG_FORMAT", "Unsupported image format")
    if fmt == "heic" and not HEIC_AVAILABLE:
        raise GlyphlabError(
            "E_IMG_FORMAT",
            "HEIC decoder unavailable",
            detail={"reason": "heic_unavailable"},
        )
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(data)) as source:
                if source.width * source.height > max_pixels:
                    raise GlyphlabError("E_IMG_TOO_LARGE", "Image exceeds pixel limit")
                source.load()
                im = ImageOps.exif_transpose(source)
                if im.mode in ("RGBA", "LA") or (im.mode == "P" and "transparency" in im.info):
                    rgba = im.convert("RGBA")
                    white = Image.new("RGBA", rgba.size, "white")
                    im = Image.alpha_composite(white, rgba)
                im = im.convert("L")
                if max(im.size) > 4500:
                    im.thumbnail((4500, 4500), Image.Resampling.LANCZOS)
                return np.asarray(im, dtype=np.uint8).copy()
    except (Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise GlyphlabError("E_IMG_TOO_LARGE", "Image exceeds pixel limit") from exc
    except (OSError, ValueError, SyntaxError, UnidentifiedImageError) as exc:
        raise GlyphlabError("E_IMG_DECODE", "Image could not be decoded") from exc

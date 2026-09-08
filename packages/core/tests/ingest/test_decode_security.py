import struct
import zlib
from io import BytesIO

import numpy as np
import pytest
from glyphlab.errors import GlyphlabError
from glyphlab.ingest.decode import decode_scan, sniff_format
from PIL import Image


def test_byte_cap_precedes_pillow(monkeypatch):
    calls = []
    monkeypatch.setattr(Image, "open", lambda *_: calls.append(1))
    with pytest.raises(GlyphlabError) as error:
        decode_scan(b"x" * (13 * 2**20))
    assert error.value.code == "E_IMG_TOO_LARGE" and calls == []


def test_bomb_header_never_loads_pixels():
    def chunk(kind, data):
        return (
            struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
        )

    png = (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", 100000, 100000, 8, 0, 0, 0, 0))
        + chunk(b"IEND", b"")
    )
    with pytest.raises(GlyphlabError) as error:
        decode_scan(png)
    assert error.value.code == "E_IMG_TOO_LARGE"


@pytest.mark.parametrize(
    "head,expected",
    [
        (b"PK\x03\x04", None),
        (b"GIF89a", None),
        (b"\x00\x00\x00\x18ftypheix", "heic"),
        (b"\x00\x00\x00\x18ftypmif1", "heic"),
        (b"\x00\x00\x00\x18ftypmsf1", "heic"),
        (b"\x00\x00\x00\x18ftypavif", None),
    ],
)
def test_magic_brands(head, expected):
    assert sniff_format(head) == expected


def test_exif_six_rotates_exact_pixel_regions():
    image = Image.new("RGB", (60, 30), "white")
    image.paste("black", (0, 0, 20, 10))
    exif = Image.Exif()
    exif[274] = 6
    data = BytesIO()
    image.save(data, format="JPEG", quality=100, exif=exif)
    decoded = decode_scan(data.getvalue())
    assert decoded.shape == (60, 30)
    assert decoded[:19, 21:].mean() < 10 and decoded[30:, :10].mean() > 250


@pytest.mark.parametrize("mode,format", [("I;16", "PNG"), ("CMYK", "JPEG")])
def test_supported_non_rgb_modes(mode, format):
    image = Image.new(mode, (16, 12))
    data = BytesIO()
    image.save(data, format=format)
    result = decode_scan(data.getvalue())
    assert result.dtype == np.uint8 and result.shape == (12, 16)


def test_downscale_preserves_aspect():
    data = BytesIO()
    Image.new("L", (5000, 100), 255).save(data, format="PNG")
    assert decode_scan(data.getvalue()).shape == (90, 4500)


def test_heic_roundtrip_and_unavailable(monkeypatch):
    heif = pytest.importorskip("pillow_heif")
    data = BytesIO()
    heif.from_pillow(Image.new("RGB", (32, 24), "white")).save(data)
    assert sniff_format(data.getvalue()[:32]) == "heic"
    assert decode_scan(data.getvalue()).shape == (24, 32)
    monkeypatch.setattr("glyphlab.ingest.decode.HEIC_AVAILABLE", False)
    with pytest.raises(GlyphlabError) as error:
        decode_scan(data.getvalue())
    assert error.value.code == "E_IMG_FORMAT" and error.value.detail == {
        "reason": "heic_unavailable"
    }

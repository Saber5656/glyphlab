from io import BytesIO

import numpy as np
import pytest
from glyphlab.errors import GlyphlabError
from glyphlab.ingest.decode import decode_scan, sniff_format
from PIL import Image


def test_invalid_limits_and_alpha():
    for value, code in [
        (b"PKzip", "E_IMG_FORMAT"),
        (b"\xff\xd8\xff", "E_IMG_DECODE"),
        (b"x" * 100, "E_IMG_TOO_LARGE"),
    ]:
        with pytest.raises(GlyphlabError) as e:
            decode_scan(value, max_bytes=50)
        assert e.value.code == code
    buf = BytesIO()
    Image.new("RGBA", (10, 8), (0, 0, 0, 0)).save(buf, format="PNG")
    result = decode_scan(buf.getvalue())
    assert result.shape == (8, 10) and np.all(result == 255)
    with pytest.raises(GlyphlabError) as e:
        decode_scan(buf.getvalue(), max_pixels=10)
    assert e.value.code == "E_IMG_TOO_LARGE"
    assert sniff_format(b"\x00\x00\x00\x18ftypheic") == "heic"


@pytest.mark.parametrize("orientation", range(1, 9))
def test_exif_orientation(orientation):
    image = Image.new("RGB", (12, 8), "white")
    image.paste((0, 0, 0), (0, 0, 4, 3))
    exif = Image.Exif()
    exif[274] = orientation
    buf = BytesIO()
    image.save(buf, format="JPEG", exif=exif, quality=100)
    result = decode_scan(buf.getvalue())
    assert result.shape == ((12, 8) if orientation >= 5 else (8, 12))

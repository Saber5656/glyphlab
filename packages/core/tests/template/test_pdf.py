from uuid import UUID

import cv2
import numpy as np
import pypdfium2 as pdfium
import pytest
from glyphlab.charset import get_preset
from glyphlab.template import generate_template
from glyphlab.template.pdf import sanitize_project_name


def test_pdf_deterministic_and_markers(tmp_path):
    args = (get_preset("ja-basic-v1"), UUID(int=1), "Test")
    a = generate_template(tmp_path / "a", *args)
    b = generate_template(tmp_path / "b", *args)
    assert a.pdf_path.read_bytes() == b.pdf_path.read_bytes()
    with pdfium.PdfDocument(a.pdf_path) as pdf:
        assert len(pdf) == 6
        assert abs(pdf[0].get_width() - 595.28) < 0.01
        assert abs(pdf[0].get_height() - 841.89) < 0.01
        img = np.asarray(pdf[0].render(scale=300 / 72).to_pil().convert("L"))
    detector = cv2.aruco.ArucoDetector(cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50))
    _, ids, _ = detector.detectMarkers(img)
    assert set(ids.flatten()) == {0, 1, 2, 3}
    assert sanitize_project_name("a\x07" * 100) == "a" * 64


@pytest.mark.parametrize(
    "charset_id", ["../../outside", "/absolute", "sub/name", "sub\\name", "bad\x00name"]
)
def test_template_rejects_unsafe_charset_filename(tmp_path, charset_id):
    from dataclasses import replace

    from glyphlab.errors import GlyphlabError

    charset = replace(get_preset("ascii"), charset_id=charset_id)
    with pytest.raises(GlyphlabError) as error:
        generate_template(tmp_path / "template", charset, UUID(int=1), "Test")
    assert error.value.code == "E_VALIDATION"


@pytest.mark.parametrize("filename", ["ascii.pdf", "template.json"])
def test_template_does_not_follow_output_symlink(tmp_path, filename):
    from glyphlab.errors import GlyphlabError

    outside = tmp_path / "outside"
    outside.write_bytes(b"preserve")
    directory = tmp_path / "template"
    directory.mkdir()
    (directory / filename).symlink_to(outside)
    with pytest.raises(GlyphlabError) as error:
        generate_template(directory, get_preset("ascii"), UUID(int=1), "Test")
    assert error.value.code == "E_VALIDATION"
    assert outside.read_bytes() == b"preserve"

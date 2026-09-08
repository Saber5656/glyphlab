from uuid import UUID

import cv2
import numpy as np
import pypdfium2 as pdfium
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
        img = np.asarray(pdf[0].render(scale=300 / 72).to_pil().convert("L"))
    detector = cv2.aruco.ArucoDetector(cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50))
    _, ids, _ = detector.detectMarkers(img)
    assert set(ids.flatten()) == {0, 1, 2, 3}
    assert sanitize_project_name("a\x07" * 100) == "a" * 64

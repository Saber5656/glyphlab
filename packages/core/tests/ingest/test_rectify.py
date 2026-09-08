import numpy as np
import pytest
from glyphlab.errors import GlyphlabError
from glyphlab.ingest.decode import decode_scan
from glyphlab.ingest.rectify import detect_and_rectify


@pytest.mark.parametrize("profile", ["clean-scan", "phone-tilt"])
@pytest.mark.parametrize("page_index", range(6))
def test_real_pdf_corpus_rectification(corpus_page, template_fixture, profile, page_index):
    data, _ = corpus_page(profile, page_index)
    page = detect_and_rectify(decode_scan(data), template_fixture[2])
    assert page.page_index == page_index
    assert page.canvas.shape == (3508, 2481)
    assert page.diagnostics["reproj_error_px"] <= 3
    assert page.diagnostics["sharpness"] >= 60


def test_missing_markers_have_diagnostics(template_fixture):
    with pytest.raises(GlyphlabError) as e:
        detect_and_rectify(np.full((600, 400), 255, np.uint8), template_fixture[2])
    assert e.value.code == "E_PAGE_NO_MARKERS"
    assert e.value.detail["attempts"] == 3


def test_crumpled_rejected(corpus_page, template_fixture):
    data, _ = corpus_page("crumpled")
    with pytest.raises(GlyphlabError) as e:
        detect_and_rectify(decode_scan(data), template_fixture[2])
    assert e.value.code in {"E_PAGE_WARPED", "E_PAGE_BLURRY", "E_PAGE_NO_MARKERS"}


def test_unknown_page_and_two_pages_in_frame(corpus_page, template_fixture):
    from dataclasses import replace

    import cv2

    sidecar = template_fixture[2]
    data0, _ = corpus_page("clean-scan", 0)
    data1, _ = corpus_page("clean-scan", 1)
    with pytest.raises(GlyphlabError) as error:
        detect_and_rectify(decode_scan(data1), replace(sidecar, pages=(sidecar.pages[0],)))
    assert error.value.code == "E_PAGE_UNKNOWN"
    image = np.hstack([cv2.resize(decode_scan(data), (1240, 1754)) for data in (data0, data1)])
    with pytest.raises(GlyphlabError) as error:
        detect_and_rectify(image, sidecar)
    assert error.value.code == "E_PAGE_AMBIGUOUS"
    assert len(error.value.detail["marker_ids"]) >= 4


def test_rectification_is_byte_deterministic(corpus_page, template_fixture):
    data, _ = corpus_page("phone-tilt")
    img = decode_scan(data)
    first = detect_and_rectify(img, template_fixture[2])
    second = detect_and_rectify(img, template_fixture[2])
    assert first.canvas.tobytes() == second.canvas.tobytes()
    assert first.diagnostics == second.diagnostics


def test_upscaled_fallback_restores_source_coordinates(monkeypatch, corpus_page, template_fixture):
    import cv2

    data, _ = corpus_page("clean-scan")
    img = cv2.resize(decode_scan(data), (1240, 1754))
    real = cv2.aruco.ArucoDetector(cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50))

    class LadderDetector:
        attempts = 0

        def detectMarkers(self, candidate):
            self.attempts += 1
            if self.attempts < 3:
                return [], None, []
            return real.detectMarkers(candidate)

    monkeypatch.setattr(cv2.aruco, "ArucoDetector", lambda *_: LadderDetector())
    page = detect_and_rectify(img, template_fixture[2])
    assert page.page_index == 0 and page.diagnostics["attempts"] == 3
    assert page.diagnostics["detection_scale"] == 1.5
    assert page.diagnostics["reproj_error_px"] <= 3

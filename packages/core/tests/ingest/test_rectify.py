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

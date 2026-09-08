import numpy as np
import pytest
from glyphlab.ingest.cells import CellGeometry, binarize_cell, slice_cells
from glyphlab.ingest.decode import decode_scan
from glyphlab.ingest.rectify import detect_and_rectify
from glyphlab.template.layout import GuideGeometry


@pytest.mark.parametrize(
    "profile,fill",
    [
        ("clean-scan", 0.0),
        ("clean-scan", 1.0),
        ("phone-tilt", 1.0),
        ("phone-dark", 1.0),
    ],
)
def test_classification_matches_manifest(corpus_page, template_fixture, profile, fill):
    data, manifest = corpus_page(profile, fill_fraction=fill)
    page = detect_and_rectify(decode_scan(data), template_fixture[2])
    outcomes = [binarize_cell(crop, geom) for geom, crop in slice_cells(page, template_fixture[2])]
    inked = {f"U+{cell.geom.codepoint:04X}" for cell in outcomes if not cell.is_empty}
    assert inked == set(manifest["inked"])
    assert all(not cell.failed for cell in outcomes)


def test_despeckle_and_checkerboard():
    geom = CellGeometry(65, "latin", (0, 0, 0), (0, 0, 250, 250), GuideGeometry(175, 95))
    dust = np.full((250, 250), 255, np.uint8)
    dust[::10, ::10] = 0
    assert binarize_cell(dust, geom).is_empty
    checker = np.indices((250, 250)).sum(axis=0) % 2 * 255
    assert binarize_cell(checker.astype(np.uint8), geom).failed


def test_custom_charset_drives_guide_class():
    from uuid import UUID

    from glyphlab.charset import CharDef, CharsetSpec
    from glyphlab.ingest.rectify import RectifiedPage
    from glyphlab.template.layout import compute_layout
    from glyphlab.template.sidecar import TemplateSidecar

    charset = CharsetSpec("Accented", 1, (CharDef(0xE9, "latin", True),))
    sidecar = TemplateSidecar(
        compute_layout(charset).pages, str(UUID(int=1)), charset.charset_id, 1
    )
    page = RectifiedPage(0, np.full((3508, 2481), 255, np.uint8), {})
    geom, _ = next(slice_cells(page, sidecar, charset))
    assert geom.script_class == "latin" and geom.guides.baseline is not None
    assert geom.guides.square is None


def test_cell_stage_performance_budget(corpus_page, template_fixture):
    from time import perf_counter

    data, _ = corpus_page("clean-scan")
    page = detect_and_rectify(decode_scan(data), template_fixture[2])
    start = perf_counter()
    cells = [binarize_cell(crop, geom) for geom, crop in slice_cells(page, template_fixture[2])]
    elapsed = perf_counter() - start
    assert len(cells) == 49 and elapsed <= 1.5

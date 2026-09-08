import pytest
from glyphlab.fit import fit_glyph
from glyphlab.ingest.cells import binarize_cell, slice_cells
from glyphlab.ingest.decode import decode_scan
from glyphlab.ingest.rectify import detect_and_rectify
from glyphlab.vectorize import TraceOpts, select_engine


@pytest.mark.parametrize(
    "cp,page_index,advance,bbox",
    [
        (65, 0, 979, (51, -163, 919, 755)),
        (120, 1, 913, (60, -192, 854, 732)),
        (0x3002, 1, 1000, (390, 253, 613, 466)),
        (0x3042, 2, 1000, (219, 43, 788, 723)),
        (0x30FC, 5, 1000, (228, 438, 776, 517)),
    ],
)
def test_real_trace_fit_integer_goldens(
    corpus_page, template_fixture, cp, page_index, advance, bbox
):
    charset, _, sidecar = template_fixture
    data, _ = corpus_page("clean-scan", page_index)
    page = detect_and_rectify(decode_scan(data), sidecar)
    geom, crop = next(
        (geom, crop) for geom, crop in slice_cells(page, sidecar, charset) if geom.codepoint == cp
    )
    cell = binarize_cell(crop, geom)
    glyph = fit_glyph(
        select_engine("potrace").trace(cell.bitmap, TraceOpts()),
        geom,
        charset.get(cp),
        cell.warnings,
    )
    assert glyph.advance == advance
    assert glyph.outline.bbox() == bbox

import json
from uuid import UUID

import pytest
from glyphlab.charset import get_preset
from glyphlab.errors import GlyphlabError
from glyphlab.template.layout import cell_box_px, compute_layout
from glyphlab.template.sidecar import read_sidecar, write_sidecar


def test_canonical_layout():
    layout = compute_layout(get_preset("ja-basic-v1"))
    assert layout.page_count == 6
    assert len(layout.pages[-1].cells_with_chars()) == 31
    assert layout.pages[0].cells[0].codepoint == 0x21
    assert layout.pages[-1].cells_with_chars()[-1].codepoint == 0x30FC
    assert cell_box_px(layout.pages[0], 0, 0) == (165, 696, 414, 945)
    for page in layout.pages:
        assert page.aruco_ids == tuple(range(page.index * 4, page.index * 4 + 4))
        for cell in page.cells:
            x0, y0, x1, y1 = page.writing_box_mm(cell.row, cell.col)
            for rect in page.marker_rects_mm():
                assert min(x1, rect[2]) <= max(x0, rect[0]) or min(y1, rect[3]) <= max(y0, rect[1])


def test_sidecar_roundtrip_and_validation(tmp_path):
    charset = get_preset("ja-basic-v1")
    layout = compute_layout(charset)
    path = tmp_path / "template.json"
    write_sidecar(path, layout, UUID(int=1), charset)
    original = path.read_bytes()
    sidecar = read_sidecar(path, expected_charset=charset)
    write_sidecar(path, sidecar, sidecar.template_id, charset)
    assert path.read_bytes() == original
    payload = json.loads(original)
    payload["pages"][0]["cells"][1]["codepoint"] = payload["pages"][0]["cells"][0]["codepoint"]
    path.write_text(json.dumps(payload))
    with pytest.raises(GlyphlabError):
        read_sidecar(path)

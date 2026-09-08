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


def test_sidecar_honors_persisted_geometry(tmp_path):
    from dataclasses import replace

    charset = get_preset("ascii")
    layout = compute_layout(charset)
    pages = tuple(replace(p, grid_mm=replace(p.grid_mm, x0=13.0)) for p in layout.pages)
    path = tmp_path / "old-layout.json"
    write_sidecar(path, replace(layout, pages=pages), UUID(int=1), charset)
    stored = read_sidecar(path, expected_charset=charset)
    assert stored.pages[0].grid_mm.x0 == 13
    assert cell_box_px(stored.pages[0], 0, 0)[0] > cell_box_px(layout.pages[0], 0, 0)[0]


@pytest.mark.parametrize("mutation", ["marker", "foreign", "schema", "nonfinite", "outside"])
def test_sidecar_tampering_rejected(tmp_path, mutation):
    charset = get_preset("ascii")
    path = tmp_path / "template.json"
    write_sidecar(path, compute_layout(charset), UUID(int=1), charset)
    payload = json.loads(path.read_text())
    if mutation == "marker":
        payload["pages"][0]["aruco_ids"][0] = 8
    elif mutation == "foreign":
        payload["charset_id"] = "kana"
    elif mutation == "schema":
        payload["schema"] = "unknown"
    elif mutation == "nonfinite":
        payload["pages"][0]["grid_mm"]["cell"] = float("nan")
    else:
        payload["pages"][0]["grid_mm"]["x0"] = 200
    path.write_text(json.dumps(payload))
    with pytest.raises(GlyphlabError) as error:
        read_sidecar(path, expected_charset=charset)
    assert error.value.code == "E_TEMPLATE_MISMATCH"

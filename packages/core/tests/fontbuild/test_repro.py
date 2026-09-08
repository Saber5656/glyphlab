from glyphlab.fontbuild.builder import build_font


def test_reproducible(golden_inputs, tmp_path, monkeypatch):
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1700000000")
    a = build_font(*golden_inputs, tmp_path / "a")
    b = build_font(*golden_inputs, tmp_path / "b")
    assert a.ttf_path.read_bytes() == b.ttf_path.read_bytes()
    assert a.woff2_path.read_bytes() == b.woff2_path.read_bytes()

import hashlib
import json
from pathlib import Path

import pytest
from glyphlab.charset import PRESETS, CharDef, CharsetSpec, UnknownCharsetError, get_preset


def test_preset_counts_and_order() -> None:
    assert (len(PRESETS["ascii"]), len(PRESETS["ascii"].drawn_chars())) == (95, 94)
    assert (len(PRESETS["kana"]), len(PRESETS["kana"].drawn_chars())) == (183, 182)
    assert (len(PRESETS["ja-basic-v1"]), len(PRESETS["ja-basic-v1"].drawn_chars())) == (278, 276)
    for spec in PRESETS.values():
        assert tuple(spec.codepoints()) == tuple(sorted(spec.codepoints()))


def test_preset_boundaries_and_classes() -> None:
    kana = PRESETS["kana"]
    assert kana.get(0x3000) == CharDef(0x3000, "punct_ja", False)
    assert kana.get(0x3041) == CharDef(0x3041, "kana", True)
    assert kana.get(0x3096) is not None
    assert kana.get(0x30A1) is not None
    assert kana.get(0x30FA) is not None
    for cp in (0x3001, 0x3002, 0x300C, 0x300D, 0x30FB):
        assert kana.get(cp) is not None and kana.get(cp).script_class == "punct_ja"
    for cp in (0x3041, 0x3096, 0x30A1, 0x30FA, 0x30FC):
        assert kana.get(cp) is not None and kana.get(cp).script_class == "kana"
    for cp in (0x007F, 0x3040, 0x3097, 0x30FD, 0x30FE, 0x309B, 0x309C):
        assert kana.get(cp) is None


def test_charset_model_invariants() -> None:
    with pytest.raises(ValueError):
        CharsetSpec("bad", 1, (CharDef(2, "latin", True), CharDef(1, "latin", True)))
    with pytest.raises(ValueError):
        CharsetSpec("bad", 1, (CharDef(0xD800, "latin", True),))
    assert 0x41 in PRESETS["ascii"]
    assert PRESETS["ascii"].get(0xFFFF) is None


def test_get_preset_error() -> None:
    with pytest.raises(UnknownCharsetError):
        get_preset("missing")


def test_preset_snapshots() -> None:
    snapshot_path = Path(__file__).parent / "snapshots" / "presets.json"
    expected = json.loads(snapshot_path.read_text())
    for charset_id, spec in PRESETS.items():
        payload = f"{charset_id}:{spec.version}:" + ",".join(
            f"{cp:04X}" for cp in spec.codepoints()
        )
        digest = hashlib.sha256(payload.encode()).hexdigest()
        assert expected[charset_id]["version"] == spec.version
        assert digest == expected[charset_id]["sha256"], (
            "presets are immutable — bump the version and update the snapshot deliberately"
        )

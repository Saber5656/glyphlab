import json
from pathlib import Path

import pytest
from glyphlab.errors import ConfigError
from glyphlab.project.config import BuildConfig, ProjectConfig, ProjectSettings
from glyphlab.project.store import ProjectStore


def make_config() -> ProjectConfig:
    return ProjectConfig(
        project=ProjectSettings(name="Project", family_name="Family", charset="ascii", version=1),
        build=BuildConfig(),
    )


def test_init_and_helpers(tmp_path: Path) -> None:
    root = tmp_path / "project"
    store = ProjectStore(root)
    store.init(make_config())
    assert sorted(path.name for path in root.iterdir()) == [
        "build",
        "glyphlab.toml",
        "glyphs",
        "scans",
        "template",
        "work",
    ]
    assert store.read_status() == {}
    assert store.glyph_svg_path(0x3042).name == "U+3042.svg"
    assert store.glyph_svg_path(0x1F600).name == "U+1F600.svg"
    with pytest.raises(ConfigError):
        store.init(make_config())


def test_atomic_status_and_scans(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = tmp_path / "project"
    store = ProjectStore(root)
    store.init(make_config())
    store.write_status({"U+0041": {"status": "auto", "warnings": [], "source": None}})
    original = (root / "glyphs/status.json").read_text()

    def fail_replace(source: str | bytes | Path, destination: str | bytes | Path) -> None:
        raise OSError("injected")

    monkeypatch.setattr("glyphlab.project.store.os.replace", fail_replace)
    with pytest.raises(OSError):
        store.write_status({"U+0042": {}})
    assert (root / "glyphs/status.json").read_text() == original
    monkeypatch.undo()
    (root / "scans/a.JPG").write_bytes(b"")
    (root / "scans/b.heic").write_bytes(b"")
    (root / "scans/c.txt").write_bytes(b"")
    assert [path.name for path in store.list_scans()] == ["a.JPG", "b.heic"]
    assert json.loads((root / "glyphs/status.json").read_text())["U+0041"]["status"] == "auto"

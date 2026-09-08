import json

import pytest
from fontTools.ttLib import TTFont
from glyphlab.cli.main import app
from glyphlab.model import Contour, CubicSegment, GlyphOutline, Point
from glyphlab.project.config import ProjectConfig
from glyphlab.project.glyph_svg import write_glyph_svg
from glyphlab.project.store import ProjectStore
from glyphlab.qa.model import QAFinding
from typer.testing import CliRunner

runner = CliRunner()


@pytest.fixture
def seeded(tmp_path):
    root = tmp_path / "project"
    store = ProjectStore(root)
    config = ProjectConfig.model_validate(
        {"project": {"name": "Test", "family_name": "Test", "charset": "ascii", "version": 1}}
    )
    store.init(config)
    points = [Point(100, 0), Point(500, 0), Point(500, 700), Point(100, 700), Point(100, 0)]
    outline = GlyphOutline(
        (
            Contour(
                tuple(CubicSegment(a, a, b, b) for a, b in zip(points, points[1:], strict=False))
            ),
        )
    )
    for cp in (65, 66, 67):
        write_glyph_svg(store.glyph_svg_path(cp), outline, cp, 600)
    store.write_status(
        {
            f"U+{cp:04X}": {"status": status, "warnings": [], "source": None}
            for cp, status in [(65, "accepted"), (66, "auto"), (67, "rejected")]
        }
    )
    return root, store


@pytest.mark.parametrize(
    "flag,expected", [("--accepted-only", {32, 65}), ("--include-unreviewed", {32, 65, 66})]
)
def test_selection_and_artifacts(seeded, flag, expected):
    root, store = seeded
    result = runner.invoke(app, ["--project", str(root), "--json", "build", flag, "--skip-bakery"])
    assert result.exit_code == 0, result.output
    data = json.loads(result.stdout)["data"]
    with TTFont(data["ttf"]) as font:
        assert set(font.getBestCmap()) == expected
    assert (store.build_dir() / "proof.html").is_file()
    assert json.loads((store.build_dir() / "qa-report.json").read_text())["passed"]


def test_batch_invalid_svgs(seeded):
    root, store = seeded
    for cp in (65, 66):
        path = store.glyph_svg_path(cp)
        path.write_text(path.read_text().replace("<path ", '<path transform="scale(1)" '))
    result = runner.invoke(app, ["--project", str(root), "--json", "build", "--skip-bakery"])
    assert result.exit_code == 3, result.output
    data = json.loads(result.stdout)["error"]
    assert data["code"] == "E_GLYPH_SVG_INVALID"
    assert set(data["detail"]["files"]) == {"U+0041.svg", "U+0042.svg"}
    assert not list(store.build_dir().glob("*.ttf"))


def test_qa_failure_keeps_diagnostics_and_proof(seeded, monkeypatch):
    root, store = seeded
    monkeypatch.setattr(
        "glyphlab.qa.run_structural_checks", lambda *args: [QAFinding("injected", "FAIL", "bad")]
    )
    result = runner.invoke(app, ["--project", str(root), "--json", "build", "--skip-bakery"])
    assert result.exit_code == 4, result.output
    assert json.loads(result.stdout)["error"]["code"] == "E_QA_FAILED"
    assert (store.build_dir() / "proof.html").exists()
    assert not json.loads((store.build_dir() / "qa-report.json").read_text())["passed"]


def test_nothing_to_build(seeded):
    root, store = seeded
    store.write_status({})
    assert runner.invoke(app, ["--project", str(root), "build"]).exit_code == 3

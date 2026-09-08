import json
from pathlib import Path

from corpus.generate import generate_corpus
from glyphlab.cli.main import app
from glyphlab.template.sidecar import read_sidecar
from typer.testing import CliRunner

runner = CliRunner()


def test_incremental_and_mixed_failure(tmp_path):
    root = tmp_path / "project"
    assert (
        runner.invoke(app, ["new", "Test", "--charset", "ascii", "--dir", str(root)]).exit_code == 0
    )
    base = ["--project", str(root), "--json"]
    template = json.loads(runner.invoke(app, [*base, "template"]).stdout)["data"]
    generate_corpus(
        Path(template["pdf"]),
        read_sidecar(Path(template["sidecar"])),
        "clean-scan",
        [0],
        42,
        root / "scans",
    )
    (root / "scans/bad.jpg").write_bytes(b"not an image")
    result = runner.invoke(app, [*base, "ingest"])
    assert result.exit_code == 3, result.output
    data = json.loads(result.stdout)["data"]
    assert len(data["pages"]) == 1
    assert data["errors"][0]["file"] == "bad.jpg"
    assert data["coverage"]["have"] == 48
    (root / "scans/bad.jpg").unlink()
    (root / "scans/page-0.png").rename(root / "scans/renamed.png")
    again = runner.invoke(app, [*base, "ingest"])
    assert again.exit_code == 0, again.output
    assert json.loads(again.stdout)["data"]["pages"] == []
    accepted = runner.invoke(app, [*base, "accept", "--all-auto"])
    assert accepted.exit_code == 0, accepted.output
    rescanned = runner.invoke(app, [*base, "ingest", "--all"])
    assert json.loads(rescanned.stdout)["data"]["pages"][0]["counts"]["skipped_accepted"] == 48
    forced = runner.invoke(app, [*base, "ingest", "--force"])
    assert json.loads(forced.stdout)["data"]["pages"][0]["counts"]["extracted"] == 48

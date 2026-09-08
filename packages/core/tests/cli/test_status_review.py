import json

import pytest
from glyphlab.cli.cmd_review import parse_codepoints
from glyphlab.cli.cmd_status import compact_ranges
from glyphlab.cli.main import app
from glyphlab.errors import GlyphlabError
from glyphlab.project.store import ProjectStore
from typer.testing import CliRunner

runner = CliRunner()


def test_parse_range_and_literals():
    assert parse_codepoints(["U+0041-U+0043", "BC"], {65, 66, 67}) == {65, 66, 67}
    assert compact_ranges([65, 66, 67, 69]) == "U+0041-U+0043, U+0045"
    with pytest.raises(GlyphlabError):
        parse_codepoints(["U+D800"], {65})


@pytest.mark.parametrize(
    "state,target,exit_code",
    [
        ("auto", "accept", 0),
        ("rejected", "accept", 0),
        ("accepted", "accept", 0),
        ("missing", "accept", 3),
        ("auto", "reject", 0),
        ("accepted", "reject", 0),
    ],
)
def test_transitions(tmp_path, state, target, exit_code):
    root = tmp_path / "p"
    assert (
        runner.invoke(app, ["new", "Test", "--dir", str(root), "--charset", "ascii"]).exit_code == 0
    )
    store = ProjectStore(root)
    store.write_status({"U+0041": {"status": state, "warnings": [], "source": None}})
    result = runner.invoke(app, ["--project", str(root), target, "A"])
    assert result.exit_code == exit_code, result.output
    if not exit_code:
        assert store.read_status()["U+0041"]["status"] == (
            "accepted" if target == "accept" else "rejected"
        )
    result = runner.invoke(app, ["--project", str(root), "--json", "status"])
    assert json.loads(result.stdout)["data"]["counts"]["total"] == 94

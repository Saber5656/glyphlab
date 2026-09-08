import json

import pytest
from glyphlab.cli.main import app
from typer.testing import CliRunner

runner = CliRunner()


@pytest.mark.parametrize(
    "args,code",
    [
        (["--ok"], 0),
        (["--raise-unexpected"], 1),
        (["--bad-param"], 2),
        (["--raise", "E_VALIDATION"], 3),
        (["--raise", "E_QA_FAILED"], 4),
    ],
)
def test_exit_codes(args, code):
    result = runner.invoke(app, ["_selftest", *args])
    assert result.exit_code == code, result.output


@pytest.mark.parametrize("args,ok", [(["--ok"], True), (["--raise", "E_VALIDATION"], False)])
def test_json(args, ok):
    result = runner.invoke(app, ["--json", "_selftest", *args])
    assert json.loads(result.stdout)["ok"] == ok
    assert not result.stderr.startswith("{")


def test_version_help():
    assert "0.1.0" in runner.invoke(app, ["--version"]).output
    assert "--project" in runner.invoke(app, ["--help"]).output

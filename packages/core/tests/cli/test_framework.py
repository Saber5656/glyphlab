import json

import pytest
from glyphlab.cli.main import app
from rich.text import Text
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


@pytest.mark.parametrize("force_terminal", [False, True])
def test_version_help(monkeypatch, force_terminal):
    monkeypatch.setattr("typer.rich_utils.FORCE_TERMINAL", force_terminal)
    monkeypatch.setattr("typer.rich_utils.COLOR_SYSTEM", "standard")
    assert "0.1.0" in runner.invoke(app, ["--version"]).output
    result = runner.invoke(app, ["--help"], color=force_terminal)
    assert result.exit_code == 0
    assert "--project" in Text.from_ansi(result.output).plain


@pytest.mark.parametrize(
    "args", [["--unknown"], ["status", "--unknown"], ["new"], ["does-not-exist"]]
)
def test_parser_failures_have_json_envelope(args):
    result = runner.invoke(app, ["--json", *args])
    assert result.exit_code == 2
    data = json.loads(result.stdout)
    assert data["ok"] is False and data["error"]["code"] == "E_USAGE"

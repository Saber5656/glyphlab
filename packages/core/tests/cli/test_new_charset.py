import json

from glyphlab.cli.main import app
from typer.testing import CliRunner

runner = CliRunner()


def test_create_and_refuse(tmp_path):
    args = ["new", "Test Hand", "--dir", str(tmp_path / "font")]
    assert runner.invoke(app, args).exit_code == 0
    assert (tmp_path / "font/glyphlab.toml").exists()
    assert runner.invoke(app, args).exit_code == 3


def test_japanese_requires_family_and_dir():
    assert runner.invoke(app, ["new", "手書き"]).exit_code == 3
    assert runner.invoke(app, ["new", "手書き", "--family-name", "Hand"]).exit_code == 3


def test_charsets():
    result = runner.invoke(app, ["--json", "charset", "show", "ja-basic-v1", "--codepoints"])
    assert result.exit_code == 0, result.output
    assert len(json.loads(result.stdout)["data"]["chars"]) == 278
    result = runner.invoke(app, ["--json", "charset", "list"])
    rows = json.loads(result.stdout)["data"]
    assert next(r for r in rows if r["id"] == "ja-basic-v1")["pages"] == 6


def test_show_reports_script_counts():
    result = runner.invoke(app, ["--json", "charset", "show", "ja-basic-v1"])
    counts = json.loads(result.stdout)["data"]["scripts"]
    assert counts["latin"] == 95
    assert sum(counts.values()) == 278

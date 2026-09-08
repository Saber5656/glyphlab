import json

from glyphlab.cli.main import app
from glyphlab.project.config import load_config, write_config
from typer.testing import CliRunner

runner = CliRunner()


def test_template_lifecycle(tmp_path):
    root = tmp_path / "project"
    assert (
        runner.invoke(app, ["new", "Test", "--charset", "ascii", "--dir", str(root)]).exit_code == 0
    )
    args = ["--project", str(root), "--json", "template"]
    result = runner.invoke(app, args)
    assert result.exit_code == 0, result.output
    first = json.loads(result.stdout)["data"]
    again = runner.invoke(app, args)
    assert json.loads(again.stdout)["data"]["template_id"] == first["template_id"]
    (root / "template/ascii.pdf").unlink()
    result = runner.invoke(app, args)
    assert result.exit_code == 0, result.output
    assert (root / "template/ascii.pdf").exists()
    assert json.loads(result.stdout)["data"]["template_id"] == first["template_id"]
    assert runner.invoke(app, args + ["--regenerate"]).exit_code == 3
    result = runner.invoke(app, args + ["--regenerate", "--yes"])
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout)["data"]["template_id"] != first["template_id"]
    config = load_config(root / "glyphlab.toml")
    config.project.charset = "kana"
    write_config(root / "glyphlab.toml", config)
    result = runner.invoke(app, args)
    assert result.exit_code == 3, result.output
    assert json.loads(result.stdout)["error"]["code"] == "E_TEMPLATE_MISMATCH"

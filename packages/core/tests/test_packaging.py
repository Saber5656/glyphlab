# ruff: noqa: S603, S607
# Test subprocesses use fixed executable names and temporary test-owned paths.
"""The distributable contains only package code and standards-compliant metadata."""

import os
import subprocess
import zipfile
from pathlib import Path

import pytest


@pytest.mark.packaging
def test_wheel_contents(tmp_path):
    root = Path(__file__).resolve().parents[3]
    subprocess.run(
        ["uv", "build", "--package", "glyphlab", "--out-dir", str(tmp_path)], cwd=root, check=True
    )
    wheel = next(tmp_path.glob("glyphlab-*.whl"))
    with zipfile.ZipFile(wheel) as archive:
        paths = archive.namelist()
        assert all(p.startswith("glyphlab/") or ".dist-info/" in p for p in paths)
        assert not any("/tests/" in p or "__pycache__" in p for p in paths)
        entry = next(p for p in paths if p.endswith("entry_points.txt"))
        assert "glyphlab = glyphlab.cli.main:app" in archive.read(entry).decode()
        assert any(p.endswith("licenses/LICENSE") for p in paths)
        assert "glyphlab/qa/allowlist.toml" in paths
        assert "glyphlab/qa/report.schema.json" in paths
    venv = tmp_path / "clean"
    subprocess.run(["uv", "venv", str(venv)], check=True)
    python = venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    subprocess.run(["uv", "pip", "install", "--python", str(python), str(wheel)], check=True)
    binary = python.with_name("glyphlab.exe" if os.name == "nt" else "glyphlab")
    result = subprocess.run(
        [str(binary), "--version"], capture_output=True, text=True, check=True, cwd=tmp_path
    )
    assert "0.1.0.dev0" in result.stdout

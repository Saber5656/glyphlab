"""Hosted fixtures must not depend on Docker Desktop's host UID mapping."""

import importlib.util
import json
from pathlib import Path
from uuid import uuid4

import pytest

ROOT = Path(__file__).resolve().parents[4]
spec = importlib.util.spec_from_file_location("e2e_sidecar", ROOT / "webui/e2e/sidecar.py")
assert spec and spec.loader
sidecar = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sidecar)


def test_reads_only_target_sidecar_without_changing_private_modes(tmp_path):
    project = str(uuid4())
    key = f"projects/{project}/artifacts/{uuid4()}"
    artifact = tmp_path / "store" / key
    artifact.parent.mkdir(parents=True)
    payload = {"schema": "glyphlab.template/1", "sentinel": "target"}
    artifact.write_text(json.dumps(payload))
    artifact.chmod(0o600)
    (artifact.parent / "template.pdf").write_bytes(b"%PDF-1.7\xff")
    other = tmp_path / "store/projects" / str(uuid4()) / "artifacts"
    other.mkdir(parents=True)
    (other / "other.json").write_text('{"schema":"glyphlab.template/1","sentinel":"other"}')
    before = artifact.stat()
    assert json.loads(sidecar.read_private_sidecar(tmp_path, project)) == payload
    assert artifact.stat().st_mode == before.st_mode
    assert artifact.stat().st_mtime_ns == before.st_mtime_ns
    missing = str(uuid4())
    (tmp_path / "store/projects" / missing / "artifacts").mkdir(parents=True)
    with pytest.raises(RuntimeError, match="Expected one"):
        sidecar.read_private_sidecar(tmp_path, missing)
    with pytest.raises(ValueError):
        sidecar.read_private_sidecar(tmp_path, "../../etc")


def test_export_uses_named_compose_project_and_checks_bind(tmp_path, monkeypatch):
    project = str(uuid4())
    calls = []
    monkeypatch.setenv("E2E_COMPOSE_PROJECT", "acceptance-isolated")

    def run(argv, **kwargs):
        calls.append((argv, kwargs))
        if argv[1] == "inspect":
            return json.dumps(
                [{"Mounts": [{"Type": "bind", "Source": str(tmp_path), "Destination": "/data"}]}]
            )
        if "ps" in argv:
            return "container-id\n"
        return '{"schema":"glyphlab.template/1"}'

    monkeypatch.setattr(sidecar.subprocess, "check_output", run)
    assert (
        json.loads(sidecar.export_sidecar(ROOT, tmp_path, project))["schema"]
        == "glyphlab.template/1"
    )
    assert calls[0][0][2:4] == ["-p", "acceptance-isolated"]
    assert calls[2][0][-5:] == ["-T", "app", "python", "-", project]
    assert "--user" not in calls[2][0]
    assert calls[2][1]["input"]
    with pytest.raises(RuntimeError, match="bind mount"):
        sidecar.export_sidecar(ROOT, tmp_path / "wrong-bind", project)


def test_export_never_hides_missing_container_or_failed_read(tmp_path, monkeypatch):
    monkeypatch.delenv("E2E_COMPOSE_PROJECT", raising=False)
    monkeypatch.setattr(sidecar.subprocess, "check_output", lambda *a, **kw: "")
    with pytest.raises(RuntimeError, match="running Compose app"):
        sidecar.export_sidecar(ROOT, tmp_path, str(uuid4()))


def test_container_read_error_propagates(tmp_path, monkeypatch):
    def run(argv, **kwargs):
        if argv[1] == "inspect":
            return json.dumps(
                [{"Mounts": [{"Type": "bind", "Source": str(tmp_path), "Destination": "/data"}]}]
            )
        if "ps" in argv:
            return "container-id"
        raise sidecar.subprocess.CalledProcessError(1, argv, stderr="sidecar read failed")

    monkeypatch.setattr(sidecar.subprocess, "check_output", run)
    with pytest.raises(sidecar.subprocess.CalledProcessError):
        sidecar.export_sidecar(ROOT, tmp_path, str(uuid4()))


def test_standalone_script_exports_existing_file(tmp_path):
    """The same stdin entrypoint used by Compose emits only JSON, without service imports."""
    import os
    import subprocess
    import sys

    project = str(uuid4())
    key = f"projects/{project}/artifacts/{uuid4()}"
    artifact = tmp_path / "store" / key
    artifact.parent.mkdir(parents=True)
    artifact.write_text('{"schema":"glyphlab.template/1"}')
    artifact.chmod(0o600)
    result = subprocess.check_output(  # noqa: S603 -- test-owned script and validated UUID
        [sys.executable, "-", project],
        input=Path(sidecar.__file__).read_text(),
        text=True,
        env={**os.environ, "GLYPHLAB_DATA_DIR": str(tmp_path)},
        timeout=10,
    )
    assert json.loads(result) == {"schema": "glyphlab.template/1"}
    assert artifact.stat().st_mode & 0o777 == 0o600


def test_sidecar_scan_rejects_duplicates_and_symlink_escape(tmp_path):
    project = str(uuid4())
    directory = tmp_path / "store/projects" / project / "artifacts"
    directory.mkdir(parents=True)
    for name in ("first", "second"):
        (directory / name).write_text('{"schema":"glyphlab.template/1"}')
    with pytest.raises(RuntimeError, match="found 2"):
        sidecar.read_private_sidecar(tmp_path, project)
    (directory / "second").unlink()
    external = tmp_path / "external"
    external.write_text('{"schema":"glyphlab.template/1"}')
    (directory / "second").symlink_to(external)
    with pytest.raises(RuntimeError, match="escaped"):
        sidecar.read_private_sidecar(tmp_path, project)

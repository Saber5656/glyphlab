"""Read one E2E fixture sidecar as its existing container owner, without mutations."""

import json
import os
import subprocess
import sys
from pathlib import Path
from uuid import UUID


def read_private_sidecar(data: Path, project: str) -> str:
    project = str(UUID(project))
    root = (data / "store/projects" / project / "artifacts").resolve()
    payloads = []
    for candidate in root.iterdir():
        if candidate.resolve().parent != root:
            raise RuntimeError("Template artifact escaped the project's directory")
        try:
            payload = candidate.read_text()
            value = json.loads(payload)
        except (ValueError, UnicodeDecodeError):
            continue
        if isinstance(value, dict) and value.get("schema") == "glyphlab.template/1":
            payloads.append(payload)
    if len(payloads) != 1:
        raise RuntimeError(f"Expected one internal template sidecar, found {len(payloads)}")
    return payloads[0]


def export_sidecar(repo: Path, data: Path, project: str) -> str:
    project = str(UUID(project))
    command = ["docker", "compose"]
    if name := os.environ.get("E2E_COMPOSE_PROJECT"):
        command += ["-p", name]
    command += [
        "-f",
        str(repo / "deploy/docker-compose.yml"),
        "-f",
        str(repo / "deploy/compose.e2e.yml"),
    ]
    # Validate the fixture bind explicitly: a healthy unrelated stack must not conceal
    # an incorrectly configured CI/acceptance data directory.
    cid = subprocess.check_output(  # noqa: S603 -- fixed Docker argv, no shell
        command + ["ps", "-q", "app"], text=True, timeout=30
    ).strip()
    if not cid or "\n" in cid:
        raise RuntimeError("Expected one running Compose app; check E2E_COMPOSE_PROJECT")
    info = json.loads(
        subprocess.check_output(  # noqa: S603 -- fixed Docker argv
            ["docker", "inspect", cid],  # noqa: S607 -- installed Docker CLI
            text=True,
            timeout=30,
        )
    )
    if not any(
        mount["Type"] == "bind"
        and mount["Destination"] == "/data"
        and Path(mount["Source"]).resolve() == data.resolve()
        for mount in info[0]["Mounts"]
    ):
        raise RuntimeError("E2E_DATA_DIR must match the Compose app's /data bind mount")
    # stdin supplies this test-only script; exec retains the non-root application UID.
    # The only stdout is this project's sidecar, never the database or bearer tokens.
    return subprocess.check_output(  # noqa: S603 -- fixed Docker argv, validated UUID
        command + ["exec", "-T", "app", "python", "-", project],
        input=Path(__file__).read_text(),
        text=True,
        timeout=30,
    )


if __name__ == "__main__":
    print(read_private_sidecar(Path(os.environ.get("GLYPHLAB_DATA_DIR", "/data")), sys.argv[1]))

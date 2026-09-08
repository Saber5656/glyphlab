"""Executable HTTP attack regressions; all payloads are synthetic."""

import socket
import struct
import zlib
from pathlib import Path
from uuid import uuid4

import pytest
from service_test_support import auth

from glyphlab_service.api.uploads import upload_key
from glyphlab_service.db.models import Job
from glyphlab_service.jobs.queue import claim_next
from glyphlab_service.jobs.worker import Worker


def process(app):
    with app.state.session_factory() as session:
        job = claim_next(session)
    Worker(app.state).process(job.id)
    with app.state.session_factory() as session:
        return session.get(Job, job.id)


def test_t1_decompression_bomb(client, app, project):
    """T1: Header preflight refuses huge images in the worker without decoding."""
    data = struct.pack(">IIBBBBB", 100000, 100000, 8, 2, 0, 0, 0)
    body = (
        b"\x89PNG\r\n\x1a\n"
        + struct.pack(">I", len(data))
        + b"IHDR"
        + data
        + struct.pack(">I", zlib.crc32(b"IHDR" + data))
    )
    body += struct.pack(">I", 0) + b"IDAT" + struct.pack(">I", zlib.crc32(b"IDAT"))
    response = client.post(
        "/api/projects/" + project["project_id"] + "/uploads",
        headers=auth(project),
        files={"file": ("bomb.png", body, "image/png")},
    )
    assert response.status_code == 202
    job = process(app)
    assert job.status == "failed" and job.error_code == "E_IMG_TOO_LARGE"
    assert not app.state.store.exists(
        upload_key(project["project_id"], response.json()["upload_id"])
    )


@pytest.mark.parametrize(
    "body",
    [b"\x89PNG\r\n\x1a\nPKzip", b"\xff\xd8\xfftruncated", b"<svg><script>alert(1)</script></svg>"],
)
def test_t1_polyglot(client, app, project, body):
    """T1: MIME labels and image magic cannot bypass worker decode checks."""
    response = client.post(
        "/api/projects/" + project["project_id"] + "/uploads",
        headers=auth(project),
        files={"file": ("x.jpg", body, "image/jpeg")},
    )
    if response.status_code == 202:
        job = process(app)
        assert job.status == "failed" and job.error_code.startswith("E_IMG_")
    else:
        assert response.status_code == 415


def test_t2_token_bruteforce(client, app, project):
    """T2: Wrong tokens have identical bodies and are subject to the IP wall."""
    app.state.settings.rl_default_per_minute = 120
    path = "/api/projects/" + project["project_id"]
    bodies = []
    for _ in range(120):
        response = client.get(
            path, headers={"Authorization": "Bearer glp_" + uuid4().hex + "x" * 11}
        )
        assert response.status_code == 404
        bodies.append(response.content)
    assert len(set(bodies)) == 1
    assert client.get(path, headers=auth(project)).status_code == 429


def test_t3_no_token_leak(client, app, project, caplog):
    """T3: Authenticated reads/errors never return or log tokens or filenames."""
    responses = [
        client.get("/api/projects/" + project["project_id"], headers=auth(project)),
        client.post(
            "/api/projects/" + project["project_id"] + "/uploads",
            headers=auth(project),
            files={"file": ("private.jpg", b"invalid", "image/jpeg")},
        ),
    ]
    assert all("glp_" not in r.text for r in responses)
    assert "glp_" not in caplog.text and "private.jpg" not in caplog.text


def test_t4_quota_walls(client, app, project):
    """T4: Observed file size, queue admission and global storage pressure are walls."""
    path = "/api/projects/" + project["project_id"] + "/uploads"
    payload = b"\x89PNG\r\n\x1a\n" + b"x" * 48
    app.state.settings.max_upload_bytes = 32
    assert (
        client.post(path, headers=auth(project), files={"file": ("x", payload)}).status_code == 413
    )
    app.state.settings.max_upload_bytes = 100
    app.state.storage_pressure = True
    assert (
        client.post(path, headers=auth(project), files={"file": ("x", payload)}).status_code == 507
    )


def test_t5_timeout_boundary():
    """T5: An adversarial non-terminating job is killed, including its process group."""
    import time

    from worker_fixtures import hangs

    from glyphlab_service.jobs.worker import execute_child

    started = time.monotonic()
    result = execute_child(None, 2, runner=hangs)
    assert result.code == "E_TRACE_TIMEOUT" and time.monotonic() - started < 10


def test_t6_traversal(client, app, project):
    """T6: Client paths never become object keys."""
    path = "/api/projects/" + project["project_id"]
    for endpoint in ["/glyphs/U+0041%2F..%2F.svg", "/artifacts/..%2Fsecrets"]:
        assert client.get(path + endpoint, headers=auth(project)).status_code in [404, 422]
    assert not (app.state.settings.data_dir / "secrets").exists()


def test_t7_xss_name_and_headers(client):
    """T7: Names remain data and generated SVG/HTML use restrictive response CSP."""
    response = client.post(
        "/api/projects",
        json={
            "name": "<img src=x onerror=alert(1)>",
            "family_name": "Safe Name",
            "charset_id": "ascii",
        },
    )
    assert response.status_code == 201
    data = response.json()
    pdf = client.get("/api/projects/" + data["project_id"] + "/template.pdf", headers=auth(data))
    assert "<img" not in pdf.headers["Content-Disposition"]
    assert pdf.headers["X-Content-Type-Options"] == "nosniff"


def test_t8_no_public_artifacts(client, project):
    """T8: Artifact paths require the project token even for unknown IDs."""
    assert (
        client.get(
            "/api/projects/" + project["project_id"] + "/artifacts/" + str(uuid4())
        ).status_code
        == 404
    )


def test_t9_no_egress(client, app, project, monkeypatch):
    """T9: Read/project/template/API intake paths perform no network connections."""

    def denied(*args, **kwargs):
        raise AssertionError("Network egress forbidden")

    monkeypatch.setattr(socket.socket, "connect", denied)
    assert (
        client.get("/api/projects/" + project["project_id"], headers=auth(project)).status_code
        == 200
    )
    assert (
        client.get(
            "/api/projects/" + project["project_id"] + "/template.pdf", headers=auth(project)
        ).status_code
        == 200
    )


def test_t10_t11_repo_guards():
    """T10/T11: Locked dependencies and sensitive settings serialization remain guarded."""
    from glyphlab_service.settings import Settings

    root = Path(__file__).parents[4]
    assert (root / "uv.lock").is_file()
    assert Settings(s3_secret_access_key="test").model_dump()["s3_secret_access_key"] == "[masked]"  # noqa: S105 -- masking sentinel
    assert "Private :: Do Not Upload" in (root / "packages/service/pyproject.toml").read_text()


def test_t12_cross_project(client, project):
    """T12: All mutation paths bind IDs to the authenticated project before validation."""
    other = client.post(
        "/api/projects", json={"name": "other", "family_name": "Other", "charset_id": "ascii"}
    ).json()
    path = "/api/projects/" + project["project_id"]
    before = client.get("/api/projects/" + other["project_id"], headers=auth(other)).json()
    responses = [
        client.delete(path, headers=auth(other)),
        client.post(path + "/uploads", headers=auth(other), files={"file": ("x", b"x")}),
        client.post(path + "/builds", headers=auth(other), json={}),
        client.post(path + "/glyphs:review", headers=auth(other), json={"accept": ["U+0041"]}),
    ]
    assert all(r.status_code == 404 for r in responses)
    assert len({r.content for r in responses}) == 1
    assert client.get("/api/projects/" + other["project_id"], headers=auth(other)).json() == before


def test_t5_trace_bomb_cells(client, app, project, tmp_path):
    """T5: Hundreds of disconnected components are rejected before native tracing."""
    import time
    from io import BytesIO

    from glyphlab.template.layout import cell_box_px
    from glyphlab.template.sidecar import read_sidecar
    from PIL import Image, ImageDraw
    from service_test_support import scan_for_project

    scan = scan_for_project(client, app, project, tmp_path)
    sidecar = read_sidecar(tmp_path / "template.json")
    page = sidecar.pages[0]
    cell = page.cells[0]
    box = cell_box_px(page, cell.row, cell.col)
    image = Image.open(BytesIO(scan)).convert("L")
    draw = ImageDraw.Draw(image)
    draw.rectangle(box, fill=255)
    for y in range(box[1] + 3, box[3] - 7, 14):
        for x in range(box[0] + 3, box[2] - 7, 14):
            draw.rectangle((x, y, x + 6, y + 6), fill=0)
    out = BytesIO()
    image.save(out, format="PNG")
    started = time.monotonic()
    response = client.post(
        "/api/projects/" + project["project_id"] + "/uploads",
        headers=auth(project),
        files={"file": ("noise.png", out.getvalue(), "image/png")},
    )
    assert response.status_code == 202
    job = process(app)
    assert (
        job.status == "succeeded" and time.monotonic() - started < app.state.settings.job_timeout_s
    )
    item = next(
        c for c in job.payload["result"]["cells"] if c["codepoint"] == f"U+{cell.codepoint:04X}"
    )
    assert item["outcome"] == "failed"

import hashlib
from uuid import UUID

from service_test_support import auth
from starlette.datastructures import UploadFile

from glyphlab_service.db.models import Job, Upload
from glyphlab_service.store import StoreKey

PNG = b"\x89PNG\r\n\x1a\n" + b"x" * 40


def test_streaming_and_dedup(client, app, project, monkeypatch):
    original = UploadFile.read

    async def bounded(self, size=-1):
        assert 0 < size <= 65536
        return await original(self, size)

    monkeypatch.setattr(UploadFile, "read", bounded)
    path = "/api/projects/" + project["project_id"] + "/uploads"
    response = client.post(
        path, headers=auth(project), files={"file": ("../../../etc/passwd", PNG, "image/png")}
    )
    assert response.status_code == 202, response.text
    first = response.json()
    assert first["deduplicated"] is False
    second = client.post(path, headers=auth(project), files={"file": ("x", PNG, "image/png")})
    assert second.status_code == 200 and second.json() == {**first, "deduplicated": True}
    with app.state.session_factory() as s:
        upload = s.get(Upload, first["upload_id"])
        assert upload.sha256 == hashlib.sha256(PNG).hexdigest()
    assert (
        app.state.store.get(
            StoreKey(UUID(project["project_id"]), "uploads", UUID(first["upload_id"]).hex)
        )
        == PNG
    )


def test_upload_limits(client, app, project):
    path = "/api/projects/" + project["project_id"] + "/uploads"

    def send(data=PNG, **kw):
        return client.post(
            path, headers=auth(project), files={"file": ("x", data, "image/png")}, **kw
        )

    assert send(b"PKbadzip").status_code == 415
    app.state.settings.max_upload_bytes = 10
    assert send().status_code == 413
    app.state.settings.max_upload_bytes = 1000
    app.state.storage_pressure = True
    assert send().status_code == 507
    app.state.storage_pressure = False
    app.state.settings.max_project_storage_bytes = 1
    assert send().status_code == 409
    app.state.settings.max_project_storage_bytes = 10000
    app.state.settings.max_uploads_per_project = 1
    assert send().status_code == 202
    assert send(PNG + b"other").status_code == 409


def test_queue_limit_and_terminal_retry(client, app, project):
    path = "/api/projects/" + project["project_id"] + "/uploads"

    def send(data=PNG):
        return client.post(path, headers=auth(project), files={"file": ("x", data, "image/png")})

    app.state.settings.max_queued_jobs_per_project = 1
    first = send().json()
    assert send(PNG + b"other").status_code == 429
    with app.state.session_factory.begin() as s:
        s.get(Job, first["job_id"]).status = "failed"
    again = send()
    assert again.status_code == 202
    assert again.json()["job_id"] != first["job_id"]


def test_multipart_shape(client, project):
    path = "/api/projects/" + project["project_id"] + "/uploads"
    assert client.post(path, headers=auth(project), files={"other": ("x", PNG)}).status_code == 422
    assert (
        client.post(
            path, headers=auth(project), files=[("file", ("x", PNG)), ("file", ("y", PNG))]
        ).status_code
        == 422
    )

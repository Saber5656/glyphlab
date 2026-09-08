import pytest
from fastapi.testclient import TestClient
from service_test_support import auth
from sqlalchemy import select

from glyphlab_service.db.migrate import upgrade
from glyphlab_service.db.models import AbuseEvent
from glyphlab_service.settings import Settings


def test_create_rate_and_size(tmp_path):
    from glyphlab_service.app import create_app

    settings = Settings(data_dir=tmp_path, trust_proxy_headers=True, rl_create_per_minute=2)
    upgrade(settings)
    with TestClient(create_app(settings, start_background=False)) as client:
        for _ in range(2):
            assert (
                client.post(
                    "/api/projects",
                    json={"name": "test", "family_name": "Test", "charset_id": "ascii"},
                ).status_code
                == 201
            )
        limited = client.post(
            "/api/projects", json={"name": "test", "family_name": "Test", "charset_id": "ascii"}
        )
        assert limited.status_code == 429 and limited.headers["Retry-After"]
        assert limited.json()["error"]["code"] == "E_RATE_LIMITED"
        assert limited.headers["X-Content-Type-Options"] == "nosniff"
        big = client.post(
            "/api/projects", content=b"x" * 65537, headers={"Fly-Client-IP": "192.0.2.2"}
        )
        assert big.status_code == 413
        assert big.json()["error"]["code"] == "E_REQUEST_TOO_LARGE"
        chunked = client.post(
            "/api/projects", content=iter([b"{}"]), headers={"Fly-Client-IP": "192.0.2.3"}
        )
        assert chunked.status_code == 411
        with client.app.state.session_factory() as s:
            assert len(s.scalars(select(AbuseEvent)).all()) == 1


def test_body_actual_size(client, app):
    response = client.post("/api/projects", content=b"x" * 65537, headers={"Content-Length": "1"})
    assert response.status_code == 413


def test_proxy_resolution(app):
    from starlette.requests import Request

    from glyphlab_service.limits import client_ip

    def req(headers):
        return Request(
            {
                "type": "http",
                "app": app,
                "client": ("192.0.2.1", 20),
                "headers": [(k.encode(), v.encode()) for k, v in headers.items()],
            }
        )

    assert client_ip(req({"x-forwarded-for": "198.51.100.1"})) == "192.0.2.1"
    app.state.settings.trust_proxy_headers = True
    assert client_ip(req({"x-forwarded-for": "forged, 198.51.100.1"})) == "198.51.100.1"
    assert (
        client_ip(req({"fly-client-ip": "203.0.113.2", "x-forwarded-for": "198.51.100.1"}))
        == "203.0.113.2"
    )
    assert (
        client_ip(req({"fly-client-ip": "bad", "x-forwarded-for": "198.51.100.1"})) == "192.0.2.1"
    )


def test_auth_rate(client, app, project):
    app.state.settings.rl_default_per_minute = 2
    path = "/api/projects/" + project["project_id"]
    for _ in range(2):
        assert client.get(path, headers=auth(project)).status_code == 200
    assert client.get(path, headers=auth(project)).status_code == 429


@pytest.mark.parametrize(
    "kind,field",
    [
        ("uploads", "rl_uploads_per_hour_project"),
        ("uploads", "rl_uploads_per_hour_ip"),
        ("builds", "rl_builds_per_hour_project"),
    ],
)
def test_endpoint_rates(client, app, project, kind, field):
    setattr(app.state.settings, field, 1)
    path = "/api/projects/" + project["project_id"] + "/" + kind
    kwargs = (
        {"files": {"file": ("x.png", b"\x89PNG\r\n\x1a\n" + b"x" * 40, "image/png")}}
        if kind == "uploads"
        else {"json": {}}
    )
    assert client.post(path, headers=auth(project), **kwargs).status_code != 429
    assert client.post(path, headers=auth(project), **kwargs).status_code == 429


def test_html_allows_authenticated_blob_previews(client, app):
    from starlette.responses import HTMLResponse

    @app.get("/test-preview")
    def preview():
        return HTMLResponse("<p>Preview</p>")

    response = client.get("/test-preview")
    policy = response.headers["Content-Security-Policy"]
    assert "img-src 'self' data: blob:" in policy
    assert "font-src 'self' data: blob:" in policy
    assert "default-src 'self'" in policy and "frame-ancestors 'none'" in policy

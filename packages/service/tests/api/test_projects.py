import hashlib
from datetime import timedelta
from uuid import uuid4

from service_test_support import auth
from sqlalchemy import select

from glyphlab_service.db.models import Glyph, Project, Tombstone, utcnow


def test_meta(client):
    assert client.get("/healthz").json() == {"ok": True}
    ja = next(c for c in client.get("/api/meta").json()["charsets"] if c["id"] == "ja-basic-v1")
    assert (ja["encoded"], ja["drawn"], ja["pages"]) == (278, 276, 6)


def test_project_token_and_seed(client, app, project):
    assert len(project["token"]) == 47
    with app.state.session_factory() as session:
        p = session.get(Project, project["project_id"])
        assert p.token_hash == hashlib.sha256(project["token"].encode()).digest()
        assert len(session.scalars(select(Glyph).where(Glyph.project_id == p.id)).all()) == 94
    response = client.get("/api/projects/" + project["project_id"], headers=auth(project))
    assert response.json()["counts"] == {"missing": 94, "auto": 0, "accepted": 0, "rejected": 0}
    assert "token" not in response.text


def test_uniform_auth_matrix(client, app, project):
    route = "/api/projects/" + project["project_id"]
    bodies = []
    for headers, path in [
        ({}, route),
        ({"Authorization": "wrong"}, route),
        ({"Authorization": "Bearer glp_" + "x" * 43}, route),
        (auth(project), "/api/projects/" + str(uuid4())),
        ({}, "/api/projects/bad-id"),
    ]:
        response = client.get(path, headers=headers)
        assert response.status_code == 404, response.text
        bodies.append(response.json())
    with app.state.session_factory.begin() as session:
        session.get(Project, project["project_id"]).expires_at = utcnow() - timedelta(seconds=1)
    expired = client.get(route, headers=auth(project))
    assert expired.status_code == 404
    assert all(b == expired.json() for b in bodies)


def test_delete_and_touch(client, app, project):
    with app.state.session_factory.begin() as session:
        row = session.get(Project, project["project_id"])
        row.last_accessed_at = utcnow() - timedelta(hours=2)
    route = "/api/projects/" + project["project_id"]
    client.get(route, headers=auth(project))
    with app.state.session_factory() as session:
        touched = session.get(Project, project["project_id"]).last_accessed_at
    client.get(route, headers=auth(project))
    with app.state.session_factory() as session:
        assert session.get(Project, project["project_id"]).last_accessed_at == touched
    assert client.delete(route, headers=auth(project)).status_code == 204
    with app.state.session_factory() as session:
        assert session.get(Project, project["project_id"]) is None
        assert session.get(Tombstone, project["project_id"])


def test_validation(client):
    response = client.post(
        "/api/projects", json={"name": "a", "family_name": "Bad\r\nHeader", "charset_id": "ascii"}
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "E_VALIDATION"

from concurrent.futures import ThreadPoolExecutor

from service_test_support import auth
from sqlalchemy import select

from glyphlab_service.db.models import Artifact


def test_template_cached_and_concurrent(client, app, project, monkeypatch):
    import glyphlab_service.api.template as template

    original = template.generate_template
    calls = []

    def count(*args, **kwargs):
        calls.append(1)
        return original(*args, **kwargs)

    monkeypatch.setattr(template, "generate_template", count)
    path = "/api/projects/" + project["project_id"] + "/template.pdf"
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: client.get(path, headers=auth(project)), range(2)))
    assert len(calls) == 1
    for response in results:
        assert response.status_code == 200, response.text
        assert response.content.startswith(b"%PDF-")
        assert (
            response.headers["Content-Disposition"]
            == 'attachment; filename="glyphlab-template-ascii.pdf"'
        )
        assert response.headers["Cache-Control"] == "private, max-age=3600"
    with app.state.session_factory() as session:
        rows = session.scalars(select(Artifact)).all()
        assert len(rows) == 2
        assert all(row.bytes > 0 and len(row.sha256) == 64 for row in rows)
    assert client.get(
        "/api/projects/" + project["project_id"] + "/artifacts", headers=auth(project)
    ).json() == {"artifacts": []}

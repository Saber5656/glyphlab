from uuid import UUID

from glyphlab.model import Contour, CubicSegment, GlyphOutline, GlyphStatus, Point
from glyphlab.model import Glyph as CoreGlyph
from glyphlab.project.glyph_svg import render_glyph_svg
from service_test_support import auth

from glyphlab_service.db.models import Glyph
from glyphlab_service.store import StoreKey


def seed(app, project, cp=65):
    points = [Point(50, 0), Point(450, 0), Point(450, 700), Point(50, 700), Point(50, 0)]
    outline = GlyphOutline(
        (
            Contour(
                tuple(CubicSegment(a, a, b, b) for a, b in zip(points, points[1:], strict=False))
            ),
        )
    )
    data = render_glyph_svg(CoreGlyph(cp, GlyphStatus.AUTO, outline, 500, [], None))
    name = f"U+{cp:04X}.svg"
    app.state.store.put(
        StoreKey(UUID(project["project_id"]), "glyphs", name), data, "image/svg+xml"
    )
    with app.state.session_factory.begin() as s:
        g = s.get(Glyph, (project["project_id"], cp))
        g.status = "auto"
        g.svg_key = name
        g.advance = 500
    return data


def test_list_pagination_review_svg(client, app, project):
    data = seed(app, project)
    path = "/api/projects/" + project["project_id"]
    listed = client.get(path + "/glyphs?status=auto", headers=auth(project)).json()["glyphs"]
    assert len(listed) == 1 and listed[0]["codepoint"] == "U+0041"
    first = client.get(path + "/glyphs?limit=10", headers=auth(project)).json()
    assert len(first["glyphs"]) == 10 and first["next_cursor"]
    assert client.get(path + "/glyphs?cursor=1114111", headers=auth(project)).json() == {
        "glyphs": []
    }
    svg = client.get(path + "/glyphs/U+0041.svg", headers=auth(project))
    assert svg.content == data
    assert svg.headers["Content-Security-Policy"] == "default-src 'none'; style-src 'unsafe-inline'"
    response = client.post(
        path + "/glyphs:review",
        headers=auth(project),
        json={"accept": ["U+0041", "U+0042", "U+FFFF"]},
    ).json()
    assert response["updated"] == 1 and len(response["errors"]) == 2
    repeat = client.post(
        path + "/glyphs:review", headers=auth(project), json={"accept": ["U+0041"]}
    ).json()
    assert repeat["unchanged"] == 1
    assert (
        client.post(
            path + "/glyphs:review",
            headers=auth(project),
            json={"accept": ["U+0041"], "reject": ["U+0041"]},
        ).status_code
        == 422
    )
    assert client.get(path + "/glyphs/U+41.svg", headers=auth(project)).status_code == 422


def test_corrupt_svg_never_served(client, app, project):
    seed(app, project)
    app.state.store.put(
        StoreKey(UUID(project["project_id"]), "glyphs", "U+0041.svg"),
        b"<svg><script>bad</script></svg>",
        "image/svg+xml",
    )
    response = client.get(
        "/api/projects/" + project["project_id"] + "/glyphs/U+0041.svg", headers=auth(project)
    )
    assert response.status_code == 500 and "<script>" not in response.text

"""Real subprocess pipeline: API bytes -> native trace -> font QA -> private artifact."""

import json
from io import BytesIO

from fontTools.ttLib import TTFont
from service_test_support import auth, process_next, scan_for_project

from glyphlab_service.api.uploads import upload_key


def test_real_journey(client, app, project, tmp_path):
    scan = scan_for_project(client, app, project, tmp_path)
    path = "/api/projects/" + project["project_id"]
    uploaded = client.post(
        path + "/uploads", headers=auth(project), files={"file": ("scan.png", scan, "image/png")}
    )
    assert uploaded.status_code == 202, uploaded.text
    ingest = process_next(app)
    assert ingest.status == "succeeded", (ingest.error_code, ingest.payload)
    assert ingest.payload["result"]["counts"]["extracted"] >= 40
    assert not app.state.store.exists(
        upload_key(project["project_id"], uploaded.json()["upload_id"])
    )
    glyphs = client.get(path + "/glyphs?status=auto", headers=auth(project)).json()["glyphs"]
    assert len(glyphs) >= 40 and glyphs[0]["svg_url"]
    accepted = glyphs[0]["codepoint"]
    assert (
        client.post(
            path + "/glyphs:review", headers=auth(project), json={"accept": [accepted]}
        ).json()["updated"]
        == 1
    )
    assert client.post(path + "/builds", headers=auth(project), json={}).status_code == 202
    build = process_next(app)
    assert build.status == "succeeded", (build.error_code, build.payload)
    artifacts = client.get(path + "/artifacts", headers=auth(project)).json()["artifacts"]
    assert {a["kind"] for a in artifacts} == {"ttf", "woff2", "proof_html", "qa_json"}
    contents = {
        a["kind"]: client.get(path + "/artifacts/" + a["id"], headers=auth(project)).content
        for a in artifacts
    }
    assert json.loads(contents["qa_json"])["passed"]
    font = TTFont(BytesIO(contents["ttf"]))
    assert 32 in font.getBestCmap()
    assert len(font.getBestCmap()) >= 41
    assert b"data:font/woff2;base64," in contents["proof_html"]
    retry = client.post(
        path + "/uploads", headers=auth(project), files={"file": ("scan.png", scan, "image/png")}
    )
    assert retry.status_code == 202
    reingest = process_next(app)
    assert reingest.status == "succeeded"
    assert reingest.payload["result"]["counts"]["skipped_accepted"] == 1

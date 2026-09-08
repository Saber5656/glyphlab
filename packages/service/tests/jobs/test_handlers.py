import hashlib
from uuid import UUID, uuid4

from sqlalchemy import select

from glyphlab_service.api.uploads import upload_key
from glyphlab_service.db.models import Artifact, Glyph, Job, Upload
from glyphlab_service.jobs.handlers import apply_result
from glyphlab_service.jobs.ipc import BuildResult, IngestResult
from glyphlab_service.store import StoreKey


def test_current_review_and_attempt_gate(app, project):
    uid = str(uuid4())
    jid = str(uuid4())
    app.state.store.put(upload_key(project["project_id"], uid), b"original", "image/png")
    with app.state.session_factory.begin() as s:
        s.add(
            Upload(
                id=uid,
                project_id=project["project_id"],
                sha256=hashlib.sha256(b"original").hexdigest(),
                bytes=8,
                mime="image/png",
            )
        )
        s.add(
            Job(
                id=jid,
                project_id=project["project_id"],
                type="ingest",
                status="running",
                attempts=2,
                payload={"upload_id": uid},
            )
        )
        s.get(Glyph, (project["project_id"], 65)).status = "accepted"
    result = IngestResult(
        {"cells": [{"codepoint": "U+0041", "outcome": "extracted"}]},
        {65: b"new"},
        {65: {"advance": 500, "warnings": []}},
    )
    apply_result(app.state, jid, result, expected_attempt=1)
    with app.state.session_factory() as s:
        assert s.get(Job, jid).status == "running"
    apply_result(app.state, jid, result, expected_attempt=2)
    with app.state.session_factory() as s:
        assert s.get(Glyph, (project["project_id"], 65)).status == "accepted"
        assert s.get(Job, jid).payload["result"]["counts"]["skipped_accepted"] == 1
    assert not app.state.store.exists(StoreKey(UUID(project["project_id"]), "glyphs", "U+0041.svg"))
    assert not app.state.store.exists(upload_key(project["project_id"], uid))


def test_qa_failure_and_latest_three_builds(app, project):
    for iteration in range(4):
        jid = str(uuid4())
        with app.state.session_factory.begin() as s:
            s.add(
                Job(
                    id=jid,
                    project_id=project["project_id"],
                    type="build",
                    status="running",
                    attempts=1,
                )
            )
        apply_result(
            app.state, jid, BuildResult(b"ttf", b"woff2", b"html", b'{"passed":false}', False)
        )
        with app.state.session_factory() as s:
            job = s.get(Job, jid)
            assert job.status == "failed" and job.error_code == "E_QA_FAILED"
            rows = s.scalars(
                select(Artifact).where(Artifact.project_id == project["project_id"])
            ).all()
            assert len(rows) == min(iteration + 1, 3) * 4
    assert len({a.job_id for a in rows}) == 3

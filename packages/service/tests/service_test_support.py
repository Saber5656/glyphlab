"""Shared HTTP journey helpers for service tests."""

from glyphlab.template.sidecar import read_sidecar
from sqlalchemy import select

from glyphlab_service.api.template import artifact_key
from glyphlab_service.db.models import Artifact, Job
from glyphlab_service.jobs.queue import claim_next
from glyphlab_service.jobs.worker import Worker


def auth(project):
    return {"Authorization": "Bearer " + project["token"]}


def scan_for_project(client, app, project, tmp_path):
    from corpus.generate import generate_corpus

    path = "/api/projects/" + project["project_id"]
    template = client.get(path + "/template.pdf", headers=auth(project))
    assert template.status_code == 200, template.text
    pdf = tmp_path / "template.pdf"
    pdf.write_bytes(template.content)
    with app.state.session_factory() as s:
        artifact = s.scalar(
            select(Artifact).where(
                Artifact.project_id == project["project_id"], Artifact.kind == "template_sidecar"
            )
        )
    sidecar_path = tmp_path / "template.json"
    sidecar_path.write_bytes(app.state.store.get(artifact_key(artifact)))
    generate_corpus(pdf, read_sidecar(sidecar_path), "clean-scan", [0], 42, tmp_path / "corpus")
    return (tmp_path / "corpus/page-0.png").read_bytes()


def process_next(app):
    with app.state.session_factory() as session:
        job = claim_next(session)
    assert job
    Worker(app.state).process(job.id)
    with app.state.session_factory() as session:
        return session.get(Job, job.id)

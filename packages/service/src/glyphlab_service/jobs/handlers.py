"""Parent-side persistence. Review state is rechecked after child work completes."""

import hashlib
from collections import Counter
from copy import deepcopy
from uuid import UUID, uuid4

from glyphlab.errors import GlyphlabError
from sqlalchemy import select

from ..api.template import artifact_key, ensure_template, get_sidecar
from ..api.uploads import upload_key
from ..db.engine import locked_session
from ..db.models import Artifact, Glyph, Job, Project, Upload, utcnow
from ..store import StoreKey
from .ipc import BuildRequest, BuildResult, ChildError, IngestRequest, IngestResult
from .queue import finish


def prepare_request(state, job_id):
    with locked_session(state.session_factory) as session:
        job = session.get(Job, job_id)
        if not job or job.status != "running":
            return None
        project = session.get(Project, job.project_id)
        rows = list(session.scalars(select(Glyph).where(Glyph.project_id == job.project_id)))
        if job.type == "ingest":
            upload = session.get(Upload, job.payload["upload_id"])
            get_sidecar(session, state.store, project)
            artifacts = ensure_template(session, state.store, project)
            upload.status = "processing"
            return IngestRequest(
                state.store.get(upload_key(project.id, upload.id)),
                state.store.get(artifact_key(artifacts["template_sidecar"])),
                project.charset_id,
                {g.codepoint: g.status for g in rows},
            )
        svgs = {
            g.codepoint: state.store.get(StoreKey(UUID(project.id), "glyphs", g.svg_key))
            for g in rows
            if g.svg_key and g.status in ["auto", "accepted"]
        }
        if not svgs:
            raise GlyphlabError(
                "E_VALIDATION", "Request failed", detail={"reason": "nothing_to_build"}
            )
        return BuildRequest(
            svgs,
            project.family_name,
            1,
            project.charset_id,
            project.name,
            {g.codepoint: g.status for g in rows},
            {g.codepoint: g.warnings for g in rows},
        )


def apply_result(state, job_id, result, *, expected_attempt=None):
    with locked_session(state.session_factory) as session:
        job = session.get(Job, job_id)
        # Deletion/recovery may have invalidated this process's result.
        if not job or job.status != "running":
            return
        if expected_attempt is not None and job.attempts != expected_attempt:
            return
        if isinstance(result, ChildError):
            finish(job, "failed", result.code)
            job.payload = {**job.payload, "result": {"detail": result.detail}}
        elif isinstance(result, IngestResult):
            report = deepcopy(result.report)
            for cp, data in result.svgs.items():
                row = session.get(Glyph, (job.project_id, cp))
                if row is None or row.status not in ["missing", "auto", "rejected"]:
                    for cell in report.get("cells", []):
                        if cell.get("codepoint") == f"U+{cp:04X}":
                            cell["outcome"] = "skipped_accepted"
                    continue
                name = f"U+{cp:04X}.svg"
                state.store.put(
                    StoreKey(UUID(job.project_id), "glyphs", name), data, "image/svg+xml"
                )
                meta = result.metadata.get(cp, {})
                row.svg_key = name
                row.status = "auto"
                row.advance = meta.get("advance")
                row.warnings = meta.get("warnings", [])
                row.source_upload_id = job.payload["upload_id"]
                row.updated_at = utcnow()
            if "cells" in report:
                counts = Counter(c["outcome"] for c in report["cells"])
                report["counts"] = {
                    k: counts[k] for k in ["extracted", "empty", "skipped_accepted", "failed"]
                }
            job.payload = {**job.payload, "result": report}
            finish(job, "succeeded")
        elif isinstance(result, BuildResult):
            artifact_ids = []
            for kind, data, mime in [
                ("ttf", result.ttf, "font/ttf"),
                ("woff2", result.woff2, "font/woff2"),
                ("proof_html", result.proof_html, "text/html"),
                ("qa_json", result.qa_json, "application/json"),
            ]:
                name = uuid4().hex
                artifact = Artifact(
                    project_id=job.project_id,
                    job_id=job.id,
                    kind=kind,
                    storage_key=name,
                    bytes=len(data),
                    sha256=hashlib.sha256(data).hexdigest(),
                )
                state.store.put(artifact_key(artifact), data, mime)
                session.add(artifact)
                session.flush()
                artifact_ids.append(artifact.id)
            job.payload = {
                **job.payload,
                "result": {"artifact_ids": artifact_ids, "qa_passed": result.qa_passed},
            }
            finish(
                job,
                "succeeded" if result.qa_passed else "failed",
                None if result.qa_passed else "E_QA_FAILED",
            )
            builds = list(
                session.scalars(
                    select(Artifact)
                    .where(Artifact.project_id == job.project_id, Artifact.job_id.is_not(None))
                    .order_by(Artifact.created_at.desc(), Artifact.id)
                )
            )
            keep = list(dict.fromkeys(a.job_id for a in builds))[:3]
            for artifact in builds:
                if artifact.job_id not in keep:
                    state.store.delete(artifact_key(artifact))
                    session.delete(artifact)
        else:
            raise TypeError("Invalid child result")
        if job.type == "ingest":
            upload = session.get(Upload, job.payload["upload_id"])
            if upload:
                upload.status = "processed" if job.status == "succeeded" else "failed"
                upload.error_code = job.error_code
                if isinstance(result, IngestResult):
                    upload.page_index = result.report.get("page_index")
                state.store.delete(upload_key(job.project_id, upload.id))


def cleanup_terminal_uploads(state):
    """Recovery backstop for a crash between job termination and original deletion."""
    with state.session_factory.begin() as session:
        jobs = session.scalars(
            select(Job).where(
                Job.type == "ingest", Job.status.in_(["succeeded", "failed", "canceled"])
            )
        ).all()
        for job in jobs:
            upload_id = job.payload.get("upload_id")
            if not upload_id:
                continue
            state.store.delete(upload_key(job.project_id, upload_id))
            upload = session.get(Upload, upload_id)
            if upload and upload.status in ["received", "processing"]:
                upload.status = "processed" if job.status == "succeeded" else "failed"
                upload.error_code = job.error_code

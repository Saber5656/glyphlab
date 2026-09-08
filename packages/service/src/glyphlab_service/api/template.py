import hashlib
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Request, Response
from glyphlab.charset import get_preset
from glyphlab.errors import GlyphlabError
from glyphlab.template import generate_template
from glyphlab.template.sidecar import read_sidecar
from sqlalchemy import select
from starlette.responses import StreamingResponse

from ..auth import require_project
from ..db.engine import locked_session
from ..db.models import Artifact, Project
from ..store import StoreKey
from .schemas import ErrorResponse

router = APIRouter()


def artifact_key(artifact):
    return StoreKey(UUID(artifact.project_id), "artifacts", artifact.storage_key)


def ensure_template(session, store, project):
    existing = {
        a.kind: a
        for a in session.scalars(
            select(Artifact).where(
                Artifact.project_id == project.id,
                Artifact.kind.in_(["template_pdf", "template_sidecar"]),
            )
        )
    }
    if existing:
        if len(existing) != 2:
            raise GlyphlabError("E_INTERNAL", "Request failed")
        return existing
    stored = []
    try:
        with TemporaryDirectory(prefix="glyphlab-template-") as tmp:
            generated = generate_template(
                out_dir=Path(tmp),
                charset=get_preset(project.charset_id),
                template_id=UUID(project.template_id),
                project_name=project.name,
            )
            for kind, path, mime in [
                ("template_pdf", generated.pdf_path, "application/pdf"),
                ("template_sidecar", generated.sidecar_path, "application/json"),
            ]:
                data = path.read_bytes()
                name = uuid4().hex
                row = Artifact(
                    project_id=project.id,
                    kind=kind,
                    storage_key=name,
                    bytes=len(data),
                    sha256=hashlib.sha256(data).hexdigest(),
                )
                key = artifact_key(row)
                store.put(key, data, mime)
                stored.append(key)
                session.add(row)
                existing[kind] = row
            session.flush()
        return existing
    except BaseException:
        for key in stored:
            store.delete(key)
        raise


def get_sidecar(session, store, project):
    artifacts = ensure_template(session, store, project)
    data = store.get(artifact_key(artifacts["template_sidecar"]))
    try:
        with TemporaryDirectory(prefix="glyphlab-sidecar-") as tmp:
            path = Path(tmp) / "template.json"
            path.write_bytes(data)
            sidecar = read_sidecar(path, expected_charset=get_preset(project.charset_id))
            if str(sidecar.template_id) != project.template_id:
                raise ValueError("Template mismatch")
            return sidecar
    except Exception as exc:
        raise GlyphlabError("E_INTERNAL", "Request failed") from exc


@router.get(
    "/projects/{project_id}/template.pdf",
    operation_id="get_template_pdf",
    response_class=Response,
    responses={
        200: {"content": {"application/pdf": {"schema": {"type": "string", "format": "binary"}}}},
        404: {"model": ErrorResponse},
    },
)
def get_template_pdf(request: Request, project: Project = Depends(require_project)):
    with locked_session(request.app.state.session_factory, project.id) as session:
        artifacts = ensure_template(session, request.app.state.store, project)
        artifact = artifacts["template_pdf"]
    filename = f"glyphlab-template-{project.charset_id}.pdf"
    return StreamingResponse(
        request.app.state.store.stream(artifact_key(artifact)),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "private, max-age=3600",
        },
    )

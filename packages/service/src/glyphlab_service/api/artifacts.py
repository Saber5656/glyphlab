import json
from importlib.resources import files
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response
from glyphlab.errors import GlyphlabError
from sqlalchemy import select
from starlette.responses import StreamingResponse

from ..auth import require_project
from ..db.models import Artifact, Project
from .projects import iso_utc
from .schemas import ArtifactList, ErrorResponse
from .template import artifact_key

router = APIRouter()
BUILD_KINDS = ["ttf", "woff2", "proof_html", "qa_json"]
QA_SCHEMA = json.loads(files("glyphlab.qa").joinpath("report.schema.json").read_text())
QA_SCHEMA.pop("$schema", None)


@router.get(
    "/projects/{project_id}/artifacts",
    response_model=ArtifactList,
    operation_id="list_artifacts",
    responses={404: {"model": ErrorResponse}},
)
def list_artifacts(request: Request, project: Project = Depends(require_project)):
    with request.app.state.session_factory() as session:
        rows = session.scalars(
            select(Artifact)
            .where(Artifact.project_id == project.id, Artifact.kind.in_(BUILD_KINDS))
            .order_by(Artifact.created_at.desc(), Artifact.id)
        ).all()
    return {
        "artifacts": [
            {
                "id": a.id,
                "kind": a.kind,
                "job_id": a.job_id,
                "bytes": a.bytes,
                "sha256": a.sha256,
                "created_at": iso_utc(a.created_at),
            }
            for a in rows
        ]
    }


@router.get(
    "/projects/{project_id}/artifacts/{artifact_id}",
    operation_id="download_artifact",
    response_class=Response,
    responses={
        200: {
            "content": {
                mime: {
                    "schema": QA_SCHEMA
                    if mime == "application/json"
                    else {"type": "string", "format": "binary"}
                }
                for mime in ["font/ttf", "font/woff2", "text/html", "application/json"]
            }
        },
        404: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
)
def download_artifact(
    artifact_id: UUID, request: Request, project: Project = Depends(require_project)
):
    with request.app.state.session_factory() as session:
        row = session.scalar(
            select(Artifact).where(
                Artifact.id == str(artifact_id),
                Artifact.project_id == project.id,
                Artifact.kind.in_(BUILD_KINDS),
            )
        )
    if row is None:
        raise GlyphlabError("E_NOT_FOUND", "Request failed")
    mime = {
        "ttf": "font/ttf",
        "woff2": "font/woff2",
        "proof_html": "text/html",
        "qa_json": "application/json",
    }[row.kind]
    filename = (
        f"{project.family_name}-v1.{row.kind}"
        if row.kind in ["ttf", "woff2"]
        else {"proof_html": "proof.html", "qa_json": "qa-report.json"}[row.kind]
    )
    disposition = "inline" if row.kind == "proof_html" else "attachment"
    headers = {
        "Content-Disposition": f'{disposition}; filename="{filename}"',
        "Content-Length": str(row.bytes),
        "Cache-Control": "private, no-store",
    }
    if row.kind == "proof_html":
        headers["Content-Security-Policy"] = "sandbox"
    return StreamingResponse(
        request.app.state.store.stream(artifact_key(row)), media_type=mime, headers=headers
    )

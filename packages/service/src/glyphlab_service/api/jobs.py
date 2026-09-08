from uuid import UUID

from fastapi import APIRouter, Depends, Request
from glyphlab.errors import GlyphlabError
from sqlalchemy import select

from ..auth import require_project
from ..db.models import Job, Project
from .schemas import ErrorResponse, JobResponse

router = APIRouter()


@router.get(
    "/projects/{project_id}/jobs/{job_id}",
    response_model=JobResponse,
    response_model_exclude_none=True,
    operation_id="get_job",
    responses={404: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
)
def get_job(job_id: UUID, request: Request, project: Project = Depends(require_project)):
    with request.app.state.session_factory() as session:
        row = session.scalar(select(Job).where(Job.id == str(job_id), Job.project_id == project.id))
    if row is None:
        raise GlyphlabError("E_NOT_FOUND", "Request failed")
    return {
        "status": row.status,
        "error_code": row.error_code,
        "result": row.payload.get("result")
        if row.status in ["succeeded", "failed", "canceled"]
        else None,
    }

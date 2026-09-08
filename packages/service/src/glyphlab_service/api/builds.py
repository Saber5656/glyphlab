from fastapi import APIRouter, Depends, Request
from glyphlab.errors import GlyphlabError
from sqlalchemy import func, select

from ..auth import require_project
from ..db.engine import locked_session
from ..db.models import Glyph, Job, Project
from .schemas import BuildRequest, BuildResponse, ErrorResponse

router = APIRouter()


@router.post(
    "/projects/{project_id}/builds",
    status_code=202,
    response_model=BuildResponse,
    operation_id="create_build",
    responses={s: {"model": ErrorResponse} for s in [404, 409, 422, 429]},
)
def create_build(body: BuildRequest, request: Request, project: Project = Depends(require_project)):
    with locked_session(request.app.state.session_factory, project.id) as session:
        active = session.scalar(
            select(Job).where(
                Job.project_id == project.id,
                Job.type == "build",
                Job.status.in_(["queued", "running"]),
            )
        )
        if active:
            raise GlyphlabError(
                "E_BUILD_IN_PROGRESS", "Request failed", detail={"job_id": active.id}
            )
        count = session.scalar(
            select(func.count())
            .select_from(Glyph)
            .where(Glyph.project_id == project.id, Glyph.status.in_(["auto", "accepted"]))
        )
        if not count:
            raise GlyphlabError(
                "E_VALIDATION", "Request failed", detail={"reason": "nothing_to_build"}
            )
        queued = session.scalar(
            select(func.count())
            .select_from(Job)
            .where(Job.project_id == project.id, Job.status == "queued")
        )
        if queued >= request.app.state.settings.max_queued_jobs_per_project:
            raise GlyphlabError("E_RATE_LIMITED", "Request failed")
        job = Job(project_id=project.id, type="build", payload={})
        session.add(job)
        session.flush()
    return {"job_id": job.id}

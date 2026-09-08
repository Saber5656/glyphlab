from datetime import UTC, timedelta

from fastapi import APIRouter, Depends, Request, Response
from glyphlab.charset import get_preset
from glyphlab.template.layout import compute_layout
from sqlalchemy import func, select

from ..auth import mint_token, require_project
from ..db.engine import locked_session
from ..db.models import Glyph, Project, utcnow
from ..purge import purge_project
from .schemas import CreateProject, ErrorResponse, ProjectCreated, ProjectResponse

router = APIRouter()


def charset_info(charset):
    return {
        "id": charset.charset_id,
        "version": charset.version,
        "encoded": len(charset.chars),
        "drawn": sum(c.drawn for c in charset.chars),
    }


def page_count(charset):
    return len(compute_layout(charset).pages)


def iso_utc(value):
    return value.replace(tzinfo=UTC)


@router.post(
    "/projects",
    status_code=201,
    response_model=ProjectCreated,
    operation_id="create_project",
    responses={422: {"model": ErrorResponse}, 429: {"model": ErrorResponse}},
)
def create_project(body: CreateProject, request: Request):
    charset = get_preset(body.charset_id)
    now = utcnow()
    token, digest = mint_token()
    project = Project(
        token_hash=digest,
        name=body.name,
        family_name=body.family_name,
        charset_id=charset.charset_id,
        charset_version=charset.version,
        created_at=now,
        last_accessed_at=now,
        expires_at=now + timedelta(days=request.app.state.settings.retention_days),
    )
    with request.app.state.session_factory.begin() as session:
        session.add(project)
        session.flush()
        session.add_all(
            [
                Glyph(project_id=project.id, codepoint=c.codepoint, status="missing")
                for c in charset.chars
                if c.drawn
            ]
        )
    return {
        "project_id": project.id,
        "token": token,
        "name": project.name,
        "family_name": project.family_name,
        "charset": charset_info(charset),
        "template_pages": page_count(charset),
        "retention_days": request.app.state.settings.retention_days,
        "expires_at": iso_utc(project.expires_at),
    }


@router.get(
    "/projects/{project_id}",
    response_model=ProjectResponse,
    operation_id="get_project",
    responses={404: {"model": ErrorResponse}},
)
def get_project(request: Request, project: Project = Depends(require_project)):
    with request.app.state.session_factory() as session:
        counts = dict(
            session.execute(
                select(Glyph.status, func.count())
                .where(Glyph.project_id == project.id)
                .group_by(Glyph.status)
            ).all()
        )
    return {
        "project_id": project.id,
        "name": project.name,
        "family_name": project.family_name,
        "charset": charset_info(get_preset(project.charset_id)),
        "counts": {s: counts.get(s, 0) for s in ["missing", "auto", "accepted", "rejected"]},
        "expires_at": iso_utc(project.expires_at),
    }


@router.delete(
    "/projects/{project_id}",
    status_code=204,
    operation_id="delete_project",
    responses={404: {"model": ErrorResponse}},
)
def delete_project(request: Request, project: Project = Depends(require_project)):
    with locked_session(request.app.state.session_factory, project.id) as session:
        purge_project(session, request.app.state.store, project.id)
    return Response(status_code=204)

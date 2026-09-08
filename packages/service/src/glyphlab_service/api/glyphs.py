import re
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response
from glyphlab.errors import GlyphlabError
from glyphlab.project.glyph_svg import read_glyph_svg
from sqlalchemy import select

from ..auth import require_project
from ..db.engine import locked_session
from ..db.models import Glyph, Project, utcnow
from ..store import StoreKey
from .projects import iso_utc
from .schemas import ErrorResponse, GlyphList, ReviewRequest, ReviewResponse, Status, WarningCode

router = APIRouter()


def parse_cp(value):
    if not re.fullmatch(r"U\+[0-9A-F]{4,6}", value):
        raise GlyphlabError("E_VALIDATION", "Request failed")
    return int(value[2:], 16)


@router.get(
    "/projects/{project_id}/glyphs",
    response_model=GlyphList,
    response_model_exclude_none=True,
    operation_id="list_glyphs",
    responses={404: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
)
def list_glyphs(
    request: Request,
    project: Project = Depends(require_project),
    status: Annotated[list[Status] | None, Query()] = None,
    warning: WarningCode | None = None,
    cursor: int = Query(-1, ge=-1, le=0x10FFFF),
    limit: int = Query(300, ge=1, le=300),
):
    query = (
        select(Glyph)
        .where(Glyph.project_id == project.id, Glyph.codepoint > cursor)
        .order_by(Glyph.codepoint)
    )
    if status:
        query = query.where(Glyph.status.in_(status))
    with request.app.state.session_factory() as session:
        rows = list(session.scalars(query))
    if warning:
        rows = [g for g in rows if warning in g.warnings]
    has_more = len(rows) > limit
    rows = rows[:limit]
    items = []
    for row in rows:
        cp = f"U+{row.codepoint:04X}"
        # Review changes updated_at but never the outline. Upload identity changes
        # only when ingestion replaces geometry; accepted glyphs keep their source.
        # Legacy rows have no source until their next ingest, so remain stable too.
        revision = row.source_upload_id or "legacy"
        items.append(
            {
                "codepoint": cp,
                "char": chr(row.codepoint),
                "status": row.status,
                "advance": row.advance,
                "warnings": row.warnings,
                "svg_url": (
                    f"/api/projects/{project.id}/glyphs/{cp}.svg?v={revision}"
                    if row.svg_key
                    else None
                ),
                "updated_at": iso_utc(row.updated_at),
            }
        )
    return {"glyphs": items, "next_cursor": rows[-1].codepoint if has_more else None}


@router.get(
    "/projects/{project_id}/glyphs/{cp}.svg",
    operation_id="get_glyph_svg",
    response_class=Response,
    responses={
        200: {"content": {"image/svg+xml": {"schema": {"type": "string"}}}},
        404: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
)
def get_glyph_svg(cp: str, request: Request, project: Project = Depends(require_project)):
    value = parse_cp(cp)
    with request.app.state.session_factory() as session:
        glyph = session.get(Glyph, (project.id, value))
    if not glyph or not glyph.svg_key:
        raise GlyphlabError("E_NOT_FOUND", "Request failed")
    data = request.app.state.store.get(StoreKey(UUID(project.id), "glyphs", glyph.svg_key))
    try:
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "glyph.svg"
            path.write_bytes(data)
            read_glyph_svg(path)
    except Exception as exc:
        raise GlyphlabError("E_INTERNAL", "Request failed") from exc
    return Response(
        data,
        media_type="image/svg+xml",
        headers={
            "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'",
            "Cache-Control": "private, max-age=60",
            "Content-Disposition": f'inline; filename="{cp}.svg"',
        },
    )


@router.post(
    "/projects/{project_id}/glyphs:review",
    response_model=ReviewResponse,
    operation_id="review_glyphs",
    responses={404: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
)
def review_glyphs(
    body: ReviewRequest, request: Request, project: Project = Depends(require_project)
):
    updated = unchanged = 0
    errors = []
    with locked_session(request.app.state.session_factory, project.id) as session:
        for action, values in [("accepted", body.accept), ("rejected", body.reject)]:
            for cp in values:
                row = session.get(Glyph, (project.id, parse_cp(cp)))
                if not row or row.status == "missing":
                    errors.append(
                        {"codepoint": cp, "reason": "missing" if row else "outside_charset"}
                    )
                elif row.status == action:
                    unchanged += 1
                else:
                    row.status = action
                    row.updated_at = utcnow()
                    updated += 1
    return {"updated": updated, "unchanged": unchanged, "errors": errors}

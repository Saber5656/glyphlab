import hashlib
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Request
from glyphlab.errors import GlyphlabError
from glyphlab.ingest.decode import sniff_format
from sqlalchemy import select
from starlette.datastructures import UploadFile
from starlette.responses import JSONResponse

from ..auth import require_project
from ..db.engine import locked_session
from ..db.models import Job, Project, Upload
from ..errors import error_response
from ..store import StoreKey
from .schemas import ErrorResponse, UploadResponse

router = APIRouter()


def upload_key(project_id, upload_id):
    return StoreKey(UUID(project_id), "uploads", UUID(upload_id).hex)


@router.post(
    "/projects/{project_id}/uploads",
    status_code=202,
    response_model=UploadResponse,
    operation_id="create_upload",
    responses={
        200: {"model": UploadResponse},
        **{s: {"model": ErrorResponse} for s in [404, 409, 413, 415, 422, 429, 507]},
    },
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "multipart/form-data": {
                    "schema": {
                        "type": "object",
                        "required": ["file"],
                        "additionalProperties": False,
                        "properties": {"file": {"type": "string", "format": "binary"}},
                    }
                }
            },
        }
    },
)
async def create_upload(request: Request, project: Project = Depends(require_project)):
    settings = request.app.state.settings
    store = request.app.state.store
    if request.app.state.storage_pressure:
        return error_response("E_QUOTA_EXCEEDED", status=507, detail={"limit": "global"})
    async with request.form(max_files=1, max_fields=0) as form:
        if (
            len(form.multi_items()) != 1
            or "file" not in form
            or not isinstance(form["file"], UploadFile)
        ):
            raise GlyphlabError("E_VALIDATION", "Request failed")
        file = form["file"]
        digest = hashlib.sha256()
        chunks = []
        size = 0
        while chunk := await file.read(65536):
            size += len(chunk)
            if size > settings.max_upload_bytes:
                raise GlyphlabError("E_IMG_TOO_LARGE", "Request failed")
            digest.update(chunk)
            chunks.append(chunk)
        data = b"".join(chunks)
        sniffed = sniff_format(data[:32])
        if not sniffed:
            raise GlyphlabError("E_IMG_FORMAT", "Request failed")
    mime = {
        "JPEG": "image/jpeg",
        "PNG": "image/png",
        "HEIC": "image/heic",
        "jpeg": "image/jpeg",
        "png": "image/png",
        "heic": "image/heic",
    }.get(str(sniffed), str(sniffed))
    with locked_session(request.app.state.session_factory, project.id) as session:
        uploads = list(session.scalars(select(Upload).where(Upload.project_id == project.id)))
        active = list(
            session.scalars(
                select(Job).where(
                    Job.project_id == project.id, Job.status.in_(["queued", "running"])
                )
            )
        )
        active_uploads = {j.payload.get("upload_id"): j for j in active if j.type == "ingest"}
        for upload in uploads:
            if upload.sha256 == digest.hexdigest() and upload.id in active_uploads:
                return JSONResponse(
                    {
                        "upload_id": upload.id,
                        "job_id": active_uploads[upload.id].id,
                        "deduplicated": True,
                    },
                    status_code=200,
                )
        live = [
            u
            for u in uploads
            if u.id in active_uploads or store.exists(upload_key(project.id, u.id))
        ]
        if len(live) >= settings.max_uploads_per_project:
            raise GlyphlabError(
                "E_QUOTA_EXCEEDED",
                "Request failed",
                detail={"limit": "uploads", "max": settings.max_uploads_per_project},
            )
        usage = sum(u.bytes for u in uploads if store.exists(upload_key(project.id, u.id)))
        # Derived objects contribute to live project storage too.
        from ..db.models import Artifact, Glyph

        usage += sum(
            a.bytes
            for a in session.scalars(select(Artifact).where(Artifact.project_id == project.id))
        )
        for glyph in session.scalars(
            select(Glyph).where(Glyph.project_id == project.id, Glyph.svg_key.is_not(None))
        ):
            usage += len(store.get(StoreKey(UUID(project.id), "glyphs", glyph.svg_key)))
        if usage + size > settings.max_project_storage_bytes:
            raise GlyphlabError("E_QUOTA_EXCEEDED", "Request failed", detail={"limit": "storage"})
        if sum(j.status == "queued" for j in active) >= settings.max_queued_jobs_per_project:
            return error_response("E_RATE_LIMITED", headers={"Retry-After": "2"})
        upload_id = str(uuid4())
        job_id = str(uuid4())
        key = upload_key(project.id, upload_id)
        store.put(key, data, mime)
        try:
            session.add(
                Upload(
                    id=upload_id,
                    project_id=project.id,
                    sha256=digest.hexdigest(),
                    bytes=size,
                    mime=mime,
                    status="received",
                )
            )
            session.add(
                Job(
                    id=job_id,
                    project_id=project.id,
                    type="ingest",
                    status="queued",
                    payload={"upload_id": upload_id},
                )
            )
            session.flush()
        except BaseException:
            store.delete(key)
            raise
    return {"upload_id": upload_id, "job_id": job_id, "deduplicated": False}

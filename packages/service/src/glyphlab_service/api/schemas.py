"""The pinned public HTTP contract (English machine responses, Japanese UI)."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Status = Literal["missing", "auto", "accepted", "rejected"]
WarningCode = Literal[
    "LOW_INK", "TOUCHES_BORDER", "TINY_CONTOURS_REMOVED", "LARGE_INK_BLOB", "OFF_GUIDE"
]
Codepoint = str


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ErrorDetail(BaseModel):
    code: str
    message: str
    detail: dict = Field(default_factory=dict)


class ErrorResponse(BaseModel):
    error: ErrorDetail


class CharsetInfo(BaseModel):
    id: str
    version: int
    encoded: int
    drawn: int


class CharsetMeta(CharsetInfo):
    pages: int


class MetaResponse(BaseModel):
    version: str
    retention_days: float
    charsets: list[CharsetMeta]


class HealthResponse(BaseModel):
    ok: bool


class CreateProject(StrictModel):
    name: str = Field(
        min_length=1,
        max_length=64,
        pattern=r"^[^\s\x00-\x1F\x7F-\x9F](?:[^\x00-\x1F\x7F-\x9F]{0,62}[^\s\x00-\x1F\x7F-\x9F])?$",
    )
    family_name: str = Field(
        min_length=1, max_length=31, pattern=r"^[A-Za-z0-9](?:[A-Za-z0-9 \-]{0,29}[A-Za-z0-9\-])?$"
    )
    charset_id: Literal["ascii", "kana", "ja-basic-v1"] = "ja-basic-v1"

    @field_validator("name")
    @classmethod
    def name_valid(cls, value):
        from glyphlab.project.config import validate_project_name

        return validate_project_name(value)

    @field_validator("family_name")
    @classmethod
    def family_valid(cls, value):
        from glyphlab.project.config import validate_family_name

        return validate_family_name(value)


class ProjectCreated(BaseModel):
    project_id: UUID
    token: str
    name: str
    family_name: str
    charset: CharsetInfo
    template_pages: int
    retention_days: float
    expires_at: datetime


class Counts(BaseModel):
    missing: int = 0
    auto: int = 0
    accepted: int = 0
    rejected: int = 0


class ProjectResponse(BaseModel):
    project_id: UUID
    name: str
    family_name: str
    charset: CharsetInfo
    counts: Counts
    expires_at: datetime


class UploadResponse(BaseModel):
    upload_id: UUID
    job_id: UUID
    deduplicated: bool


class JobResponse(BaseModel):
    status: Literal["queued", "running", "succeeded", "failed", "canceled"]
    error_code: str | None = None
    result: dict | None = None


class GlyphResponse(BaseModel):
    codepoint: str
    char: str
    status: Status
    advance: int | None = None
    warnings: list[WarningCode]
    svg_url: str | None = None
    updated_at: datetime


class GlyphList(BaseModel):
    glyphs: list[GlyphResponse]
    next_cursor: int | None = None


class ReviewRequest(StrictModel):
    accept: list[str] = Field(default_factory=list, max_length=400)
    reject: list[str] = Field(default_factory=list, max_length=400)

    @model_validator(mode="after")
    def validate_batch(self):
        import re

        values = self.accept + self.reject
        if (
            len(values) > 400
            or len(values) != len(set(values))
            or any(not re.fullmatch(r"U\+[0-9A-F]{4,6}", v) for v in values)
        ):
            raise ValueError("Invalid or duplicate codepoints")
        return self


class ReviewError(BaseModel):
    codepoint: str
    reason: str


class ReviewResponse(BaseModel):
    updated: int
    unchanged: int
    errors: list[ReviewError]


class BuildRequest(StrictModel):
    pass


class BuildResponse(BaseModel):
    job_id: UUID


class ArtifactResponse(BaseModel):
    id: UUID
    kind: Literal["ttf", "woff2", "proof_html", "qa_json"]
    job_id: UUID | None
    bytes: int
    sha256: str
    created_at: datetime


class ArtifactList(BaseModel):
    artifacts: list[ArtifactResponse]

"""Portable schema. Datetimes are naive UTC in both SQLite and PostgreSQL."""

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utcnow():
    return datetime.now(UTC).replace(tzinfo=None)


def new_id():
    return str(uuid4())


class Base(DeclarativeBase):
    pass


class Project(Base):
    __tablename__ = "projects"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    token_hash: Mapped[bytes] = mapped_column(LargeBinary(32), unique=True)
    name: Mapped[str] = mapped_column(Text)
    family_name: Mapped[str] = mapped_column(Text)
    charset_id: Mapped[str] = mapped_column(Text)
    charset_version: Mapped[int] = mapped_column(Integer, default=1)
    template_id: Mapped[str] = mapped_column(String(36), default=new_id)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    last_accessed_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime, index=True)


class Upload(Base):
    __tablename__ = "uploads"
    __table_args__ = (
        CheckConstraint(
            "status IN ('received','processing','processed','failed')",
            name="upload_status",
        ),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    sha256: Mapped[str] = mapped_column(String(64))
    bytes: Mapped[int] = mapped_column(Integer)
    mime: Mapped[str] = mapped_column(Text)
    page_index: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(16), default="received")
    error_code: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Glyph(Base):
    __tablename__ = "glyphs"
    __table_args__ = (
        CheckConstraint("status IN ('missing','auto','accepted','rejected')", name="glyph_status"),
    )
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True
    )
    codepoint: Mapped[int] = mapped_column(Integer, primary_key=True)
    status: Mapped[str] = mapped_column(String(16), default="missing")
    advance: Mapped[int | None] = mapped_column(Integer)
    warnings: Mapped[list] = mapped_column(JSON, default=list)
    svg_key: Mapped[str | None] = mapped_column(Text)
    source_upload_id: Mapped[str | None] = mapped_column(
        ForeignKey("uploads.id", ondelete="SET NULL")
    )
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('queued','running','succeeded','failed','canceled')",
            name="job_status",
        ),
        CheckConstraint("type IN ('ingest','build')", name="job_type"),
        Index("ix_jobs_status_created_at", "status", "created_at"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    type: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(16), default="queued")
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    error_code: Mapped[str | None] = mapped_column(Text)
    attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)


class Artifact(Base):
    __tablename__ = "artifacts"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('template_pdf','template_sidecar','ttf','woff2','proof_html','qa_json')",
            name="artifact_kind",
        ),
        Index("ix_artifacts_project_kind", "project_id", "kind"),
        Index(
            "uq_artifacts_template",
            "project_id",
            "kind",
            unique=True,
            sqlite_where=text("kind IN ('template_pdf','template_sidecar')"),
            postgresql_where=text("kind IN ('template_pdf','template_sidecar')"),
        ),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    job_id: Mapped[str | None] = mapped_column(String(36), index=True)
    kind: Mapped[str] = mapped_column(String(32))
    storage_key: Mapped[str] = mapped_column(Text)
    bytes: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Tombstone(Base):
    __tablename__ = "tombstones"
    project_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    purged_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class AbuseEvent(Base):
    __tablename__ = "abuse_events"
    __table_args__ = (
        CheckConstraint("kind IN ('rate_limited','auth_miss','quota')", name="abuse_kind"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    ip: Mapped[str] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(String(16))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

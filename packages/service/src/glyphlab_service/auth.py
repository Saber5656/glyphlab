"""Uniform 404 bearer authentication, including invalid IDs before body validation."""

import base64
import hashlib
import hmac
import re
import secrets
from datetime import timedelta
from uuid import UUID

from fastapi import Depends, Request
from fastapi.security import HTTPBearer
from glyphlab.errors import GlyphlabError
from sqlalchemy import update

from .db.models import AbuseEvent, Project, utcnow

bearer = HTTPBearer(auto_error=False, scheme_name="bearerAuth")


def mint_token():
    token = "glp_" + base64.urlsafe_b64encode(secrets.token_bytes(32)).rstrip(b"=").decode("ascii")
    return token, hashlib.sha256(token.encode("ascii")).digest()


def authenticate(state, project_id, authorization, ip):
    valid = bool(re.fullmatch(r"Bearer glp_[A-Za-z0-9_-]{43}", authorization or ""))
    token = authorization[7:] if valid else ""
    digest = hashlib.sha256(token.encode("ascii")).digest()
    try:
        identifier = str(UUID(project_id))
    except (ValueError, TypeError):
        identifier = "00000000-0000-0000-0000-000000000000"
    with state.session_factory() as session:
        project = session.get(Project, identifier)
        matches = hmac.compare_digest(project.token_hash if project else b"\0" * 32, digest)
        now = utcnow()
        if not valid or not matches or project is None or project.expires_at < now:
            session.add(AbuseEvent(ip=ip, kind="auth_miss"))
            session.commit()
            raise GlyphlabError("E_NOT_FOUND", "Request failed")
        if project.last_accessed_at < now - timedelta(hours=1):
            session.execute(
                update(Project)
                .where(
                    Project.id == identifier, Project.last_accessed_at < now - timedelta(hours=1)
                )
                .values(
                    last_accessed_at=now,
                    expires_at=now + timedelta(days=state.settings.retention_days),
                )
            )
            session.commit()
            session.refresh(project)
        session.expunge(project)
        return project


def require_project(project_id: UUID, request: Request, credentials=Depends(bearer)) -> Project:
    return request.state.project

import hashlib
import os
from datetime import timedelta
from uuid import uuid4

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from glyphlab_service.db.engine import make_engine, make_session_factory
from glyphlab_service.db.migrate import config, upgrade
from glyphlab_service.db.models import (
    Artifact,
    Base,
    Glyph,
    Job,
    Project,
    Tombstone,
    Upload,
    utcnow,
)
from glyphlab_service.settings import Settings


@pytest.fixture(params=["sqlite"] + (["postgres"] if os.getenv("TEST_POSTGRES_URL") else []))
def database(request, tmp_path):
    settings = Settings(
        data_dir=tmp_path,
        database_url=os.environ["TEST_POSTGRES_URL"] if request.param == "postgres" else "",
    )
    upgrade(settings)
    engine = make_engine(settings)
    yield settings, engine, make_session_factory(engine)
    command.downgrade(config(settings), "base")
    engine.dispose()


def project():
    return Project(
        id=str(uuid4()),
        token_hash=hashlib.sha256(os.urandom(32)).digest(),
        name="test",
        family_name="Test",
        charset_id="ascii",
        expires_at=utcnow() + timedelta(days=14),
    )


def test_constraints_and_cascade(database):
    _, _engine, factory = database
    p = project()
    with factory.begin() as s:
        s.add(p)
    with pytest.raises(IntegrityError), factory.begin() as s:
        s.add(Upload(project_id=str(uuid4()), sha256="0" * 64, bytes=1, mime="image/png"))
    with pytest.raises(IntegrityError), factory.begin() as s:
        s.add(Job(project_id=p.id, type="build", status="impossible"))
    with pytest.raises(IntegrityError), factory.begin() as s:
        q = project()
        q.token_hash = p.token_hash
        s.add(q)
    with factory.begin() as s:
        s.add_all(
            [
                Upload(project_id=p.id, sha256="0" * 64, bytes=1, mime="image/png"),
                Glyph(project_id=p.id, codepoint=65),
                Job(project_id=p.id, type="build"),
                Artifact(
                    project_id=p.id,
                    kind="ttf",
                    storage_key="0" * 32,
                    bytes=1,
                    sha256="0" * 64,
                ),
                Tombstone(project_id=p.id),
            ]
        )
    with factory.begin() as s:
        s.delete(s.get(Project, p.id))
    with factory() as s:
        for model in [Upload, Glyph, Job, Artifact]:
            assert not s.scalars(select(model)).all()
        assert s.get(Tombstone, p.id)


def test_migration_cycle_and_drift(database):
    settings, engine, _ = database
    with engine.connect() as conn:
        assert compare_metadata(MigrationContext.configure(conn), Base.metadata) == []
    command.downgrade(config(settings), "base")
    command.upgrade(config(settings), "head")
    with engine.connect() as conn:
        assert compare_metadata(MigrationContext.configure(conn), Base.metadata) == []

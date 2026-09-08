import hashlib
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from uuid import uuid4

import pytest
from alembic import command

from glyphlab_service.db.engine import make_engine, make_session_factory
from glyphlab_service.db.migrate import config, upgrade
from glyphlab_service.db.models import Job, Project, utcnow
from glyphlab_service.jobs.queue import claim_next, requeue_expired
from glyphlab_service.settings import Settings


@pytest.mark.parametrize(
    "database_url",
    [""] + ([os.environ["TEST_POSTGRES_URL"]] if os.getenv("TEST_POSTGRES_URL") else []),
)
def test_atomic_claim_and_lease(tmp_path, database_url):
    settings = Settings(data_dir=tmp_path, database_url=database_url)
    upgrade(settings)
    engine = make_engine(settings)
    factory = make_session_factory(engine)
    pid = str(uuid4())
    with factory.begin() as s:
        s.add(
            Project(
                id=pid,
                token_hash=hashlib.sha256(b"test").digest(),
                name="test",
                family_name="Test",
                charset_id="ascii",
                expires_at=utcnow() + timedelta(days=14),
            )
        )
    with factory.begin() as s:
        s.add_all([Job(project_id=pid, type="build") for _ in range(100)])

    def claim_all(_):
        ids = []
        while True:
            with factory() as s:
                job = claim_next(s)
                if job is None:
                    return ids
                ids.append(job.id)

    with ThreadPoolExecutor(max_workers=8) as pool:
        ids = sum(pool.map(claim_all, range(8)), [])
    assert len(ids) == len(set(ids)) == 100
    with factory.begin() as s:
        job = s.get(Job, ids[0])
        assert job.attempts == 1
        job.lease_expires_at = utcnow() - timedelta(seconds=1)
    with factory() as s:
        assert requeue_expired(s) == 1
    with factory() as s:
        job = claim_next(s)
        assert job.id == ids[0]
        assert job.attempts == 2
    with factory.begin() as s:
        s.get(Job, ids[0]).lease_expires_at = utcnow() - timedelta(seconds=1)
    with factory() as s:
        assert requeue_expired(s) == 1
    with factory() as s:
        job = s.get(Job, ids[0])
        assert job.status == "failed"
        assert job.error_code == "E_JOB_LOST"
    command.downgrade(config(settings), "base")
    engine.dispose()

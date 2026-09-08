"""Database queue: claim is the only operation incrementing attempts."""

from datetime import timedelta

from sqlalchemy import select, text

from ..db.models import Job, utcnow


def claim_next(session):
    if session.bind.dialect.name == "sqlite":
        session.execute(text("BEGIN IMMEDIATE"))
    query = select(Job).where(Job.status == "queued").order_by(Job.created_at, Job.id).limit(1)
    if session.bind.dialect.name != "sqlite":
        query = query.with_for_update(skip_locked=True)
    job = session.scalar(query)
    if job:
        job.status = "running"
        job.attempts += 1
        job.started_at = utcnow()
        job.lease_expires_at = utcnow() + timedelta(seconds=180)
    session.commit()
    return job


def finish(job, status, error_code=None, now=None):
    job.status = status
    job.error_code = error_code
    job.finished_at = now or utcnow()
    job.lease_expires_at = None


def requeue_expired(session, now=None):
    now = now or utcnow()
    if session.bind.dialect.name == "sqlite":
        session.execute(text("BEGIN IMMEDIATE"))
    query = select(Job).where(Job.status == "running", Job.lease_expires_at < now)
    if session.bind.dialect.name != "sqlite":
        query = query.with_for_update(skip_locked=True)
    jobs = list(session.scalars(query))
    for job in jobs:
        if job.attempts < 2:
            job.status = "queued"
            job.lease_expires_at = None
        else:
            finish(job, "failed", "E_JOB_LOST", now=now)
    session.commit()
    return len(jobs)

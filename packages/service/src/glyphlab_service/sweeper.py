"""Retention is store-first and each project has its own retryable transaction."""

import asyncio
import json
import logging
import threading
import time
from datetime import timedelta

from sqlalchemy import delete, select

from .db.engine import locked_session
from .db.models import AbuseEvent, Project, Tombstone, utcnow
from .jobs.handlers import cleanup_terminal_uploads
from .jobs.queue import requeue_expired
from .purge import purge_project
from .store import LocalDiskStore


class Sweeper:
    def __init__(self, session_factory, store, settings, app_state, now=utcnow):
        self.factory = session_factory
        self.store = store
        self.settings = settings
        self.state = app_state
        self.now = now
        self.task = None
        self.lock = threading.Lock()

    def start(self):
        if self.task and not self.task.done():
            return
        self.task = asyncio.create_task(self.run(), name="glyphlab-sweeper")

    async def stop(self):
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass

    async def run(self):
        await asyncio.sleep(60)
        while True:
            await asyncio.to_thread(self.tick)
            await asyncio.sleep(self.settings.sweep_interval_s)

    def tick(self):
        if not self.lock.acquire(blocking=False):
            return None
        start = time.monotonic()
        now = self.now()
        swept = 0
        try:
            with self.factory() as session:
                requeued = requeue_expired(session, now)
            cleanup_terminal_uploads(self.state)
            with self.factory() as session:
                ids = session.scalars(
                    select(Project.id)
                    .where(Project.expires_at < now)
                    .order_by(Project.expires_at)
                    .limit(50)
                ).all()
            for pid in ids:
                try:
                    with locked_session(self.factory, pid) as session:
                        project = session.get(Project, pid)
                        if project and project.expires_at < now:
                            purge_project(session, self.store, pid, now)
                            swept += 1
                except Exception:
                    logging.getLogger("glyphlab_service").error(
                        "Project purge deferred",
                        extra={"project_id": pid, "error_code": "E_INTERNAL"},
                    )
            with self.factory.begin() as session:
                tombstones = session.execute(
                    delete(Tombstone).where(Tombstone.purged_at < now - timedelta(days=30))
                ).rowcount
                abuse = session.execute(
                    delete(AbuseEvent).where(AbuseEvent.created_at < now - timedelta(days=7))
                ).rowcount
            if isinstance(self.store, LocalDiskStore):
                usage = sum(p.stat().st_size for p in self.store.root.rglob("*") if p.is_file())
                self.state.storage_pressure = usage > self.settings.max_store_bytes
            else:
                self.state.storage_pressure = False
            result = {
                "swept": swept,
                "requeued": requeued,
                "tombstones_trimmed": tombstones,
                "abuse_trimmed": abuse,
                "duration_ms": round((time.monotonic() - start) * 1000, 1),
            }
            logging.getLogger("glyphlab_service").info(json.dumps(result))
            return result
        except Exception:
            logging.getLogger("glyphlab_service").error(
                "Retention sweep deferred", extra={"error_code": "E_INTERNAL"}
            )
            return None
        finally:
            self.lock.release()

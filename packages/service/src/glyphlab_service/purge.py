"""Store-first purge: crash after object removal leaves rows to retry next sweep."""

from uuid import UUID

from .db.models import Project, Tombstone, utcnow


def purge_project(session, store, project_id, now=None):
    store.delete_prefix(UUID(project_id))
    project = session.get(Project, project_id)
    if project:
        session.delete(project)
        session.flush()
        session.merge(Tombstone(project_id=project_id, purged_at=now or utcnow()))

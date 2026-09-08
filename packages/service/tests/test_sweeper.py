import asyncio
from datetime import timedelta
from uuid import UUID

from service_test_support import auth

from glyphlab_service.db.models import AbuseEvent, Project, Tombstone, utcnow
from glyphlab_service.store import StoreKey
from glyphlab_service.sweeper import Sweeper


def test_expiry_and_trim(client, app, project):
    now = utcnow()
    with app.state.session_factory.begin() as s:
        s.get(Project, project["project_id"]).expires_at = now - timedelta(seconds=1)
        s.add(AbuseEvent(ip="192.0.2.1", kind="auth_miss", created_at=now - timedelta(days=8)))
    key = StoreKey(UUID(project["project_id"]), "uploads", "0" * 32)
    app.state.store.put(key, b"private", "image/png")
    sweeper = Sweeper(
        app.state.session_factory, app.state.store, app.state.settings, app.state, now=lambda: now
    )
    result = sweeper.tick()
    assert result["swept"] == 1 and result["abuse_trimmed"] == 1
    assert not app.state.store.exists(key)
    with app.state.session_factory() as s:
        assert s.get(Tombstone, project["project_id"])
    sweeper.now = lambda: now + timedelta(days=31)
    assert sweeper.tick()["tombstones_trimmed"] == 1


def test_failed_store_purge_retries(client, app, project, monkeypatch):
    now = utcnow()
    with app.state.session_factory.begin() as s:
        s.get(Project, project["project_id"]).expires_at = now - timedelta(seconds=1)
    original = app.state.store.delete_prefix

    def failed(pid):
        raise OSError("injected")

    monkeypatch.setattr(app.state.store, "delete_prefix", failed)
    sweeper = Sweeper(
        app.state.session_factory, app.state.store, app.state.settings, app.state, now=lambda: now
    )
    assert sweeper.tick()["swept"] == 0
    with app.state.session_factory() as s:
        assert s.get(Project, project["project_id"])
    monkeypatch.setattr(app.state.store, "delete_prefix", original)
    assert sweeper.tick()["swept"] == 1


def test_watermark_and_double_start(client, app, project):
    app.state.settings.max_store_bytes = 1
    app.state.store.put(
        StoreKey(UUID(project["project_id"]), "uploads", "0" * 32), b"xx", "image/png"
    )
    sweeper = Sweeper(app.state.session_factory, app.state.store, app.state.settings, app.state)
    sweeper.tick()
    assert app.state.storage_pressure
    assert (
        client.post(
            "/api/projects/" + project["project_id"] + "/uploads",
            headers=auth(project),
            files={"file": ("x", b"x")},
        ).status_code
        == 507
    )

    async def lifecycle():
        sweeper.start()
        task = sweeper.task
        sweeper.start()
        assert sweeper.task is task
        await sweeper.stop()

    asyncio.run(lifecycle())

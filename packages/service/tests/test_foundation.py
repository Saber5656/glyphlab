from uuid import uuid4

import pytest
from sqlalchemy import inspect, text

from glyphlab_service.db.engine import make_engine
from glyphlab_service.db.migrate import upgrade
from glyphlab_service.settings import Settings
from glyphlab_service.store import LocalDiskStore, StoreKey


def test_settings_secrets_masked():
    settings = Settings(database_url="postgresql://private", s3_secret_access_key="secret")
    assert settings.model_dump()["database_url"] == "[masked]"
    assert "private" not in repr(settings)
    assert "secret'" not in repr(settings)
    with pytest.raises(ValueError):
        Settings(retention_days=0)


def test_database_migration_and_pragmas(tmp_path):
    settings = Settings(data_dir=tmp_path)
    upgrade(settings)
    engine = make_engine(settings)
    assert set(inspect(engine).get_table_names()) >= {
        "projects",
        "uploads",
        "glyphs",
        "jobs",
        "artifacts",
        "tombstones",
        "abuse_events",
    }
    with engine.connect() as conn:
        assert conn.scalar(text("PRAGMA foreign_keys")) == 1
        assert conn.scalar(text("PRAGMA journal_mode")) == "wal"
    engine.dispose()


def test_store_roundtrip_and_traversal(tmp_path):
    store = LocalDiskStore(tmp_path)
    key = StoreKey(uuid4(), "uploads", uuid4().hex)
    store.put(key, b"\x00content", "image/png")
    assert store.get(key) == b"\x00content"
    assert b"".join(store.stream(key)) == b"\x00content"
    assert store.delete_prefix(key.project_id) == 1
    assert not store.exists(key)
    for name in [".", "..", "../../etc/passwd", "a/b"]:
        with pytest.raises(ValueError):
            StoreKey(uuid4(), "uploads", name)

from contextlib import contextmanager

from sqlalchemy import create_engine, event, select, text
from sqlalchemy.orm import sessionmaker

from .models import Project


def make_engine(settings):
    url = settings.resolved_database_url
    if url.startswith("sqlite"):
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        engine = create_engine(url, connect_args={"timeout": 30, "check_same_thread": False})

        @event.listens_for(engine, "connect")
        def pragmas(dbapi_connection, _):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.close()

        return engine
    return create_engine(url, pool_pre_ping=True)


def make_session_factory(engine):
    return sessionmaker(engine, expire_on_commit=False)


@contextmanager
def locked_session(factory, project_id=None):
    """Serialize check-and-write transactions before any read on SQLite."""
    with factory() as session:
        if session.bind.dialect.name == "sqlite":
            session.execute(text("BEGIN IMMEDIATE"))
        elif project_id:
            session.execute(select(Project).where(Project.id == project_id).with_for_update())
        try:
            yield session
            session.commit()
        except BaseException:
            session.rollback()
            raise

from alembic import context

from glyphlab_service.db.engine import make_engine
from glyphlab_service.db.models import Base
from glyphlab_service.settings import Settings

settings = context.config.attributes.get("settings") or Settings()
if context.is_offline_mode():
    context.configure(
        url=settings.resolved_database_url,
        target_metadata=Base.metadata,
        literal_binds=True,
    )
    with context.begin_transaction():
        context.run_migrations()
else:
    engine = make_engine(settings)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=Base.metadata)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()

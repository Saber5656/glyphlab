"""Application factory. Operators run migrations explicitly before starting."""

import logging
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from glyphlab.charset import get_preset
from sqlalchemy import text
from starlette.responses import FileResponse

from . import __version__
from .api import artifacts, builds, glyphs, jobs, projects, template, uploads
from .api.schemas import ErrorResponse, HealthResponse, MetaResponse
from .db.engine import make_engine, make_session_factory
from .errors import install_error_handlers
from .limits import SecurityMiddleware
from .logging import configure_logging
from .settings import Settings
from .store import StoreKey, make_store


class SPAFiles(StaticFiles):
    async def get_response(self, path, scope):
        if path.startswith("api/"):
            from starlette.exceptions import HTTPException

            raise HTTPException(404)
        try:
            return await super().get_response(path, scope)
        except Exception as exc:
            from starlette.exceptions import HTTPException

            if (
                isinstance(exc, HTTPException)
                and exc.status_code == 404
                and "." not in path.rsplit("/", 1)[-1]
            ):
                return FileResponse(self.directory / "index.html")
            raise


def create_app(settings: Settings | None = None, *, start_background=True):
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app):
        if start_background:
            from .jobs.worker import Worker
            from .sweeper import Sweeper

            worker = Worker(app.state)
            sweeper = Sweeper(app.state.session_factory, app.state.store, settings, app.state)
            worker.start()
            sweeper.start()
        try:
            yield
        finally:
            if start_background:
                await sweeper.stop()
                worker.stop()
            app.state.engine.dispose()

    app = FastAPI(
        title="glyphlab API",
        version=__version__,
        docs_url="/api/docs" if settings.environment == "dev" else None,
        redoc_url=None,
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
    )
    configure_logging()
    app.state.settings = settings
    app.state.engine = make_engine(settings)
    app.state.session_factory = make_session_factory(app.state.engine)
    app.state.store = make_store(settings)
    app.state.storage_pressure = False
    install_error_handlers(app)
    for router in [
        projects.router,
        template.router,
        uploads.router,
        glyphs.router,
        builds.router,
        artifacts.router,
        jobs.router,
    ]:
        app.include_router(router, prefix="/api", responses={500: {"model": ErrorResponse}})

    @app.get(
        "/healthz",
        response_model=HealthResponse,
        operation_id="healthz",
        responses={s: {"model": ErrorResponse} for s in [411, 413, 429, 500]},
    )
    def healthz():
        with app.state.engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        key = StoreKey(uuid4(), "artifacts", uuid4().hex)
        try:
            app.state.store.put(key, b"health", "application/octet-stream")
            if app.state.store.get(key) != b"health":
                raise RuntimeError("Storage probe mismatch")
        finally:
            app.state.store.delete_prefix(key.project_id)
        return {"ok": True}

    @app.get(
        "/api/meta",
        response_model=MetaResponse,
        operation_id="get_meta",
        responses={s: {"model": ErrorResponse} for s in [411, 413, 429, 500]},
    )
    def get_meta():
        return {
            "version": __version__,
            "retention_days": settings.retention_days,
            "charsets": [
                {
                    **projects.charset_info(get_preset(name)),
                    "pages": projects.page_count(get_preset(name)),
                }
                for name in ["ascii", "kana", "ja-basic-v1"]
            ],
        }

    if settings.webui_dist.is_dir():
        app.mount("/", SPAFiles(directory=settings.webui_dist, html=True), name="webui")
    else:
        logging.getLogger("glyphlab_service").warning("Web UI build absent; serving API only")
    if settings.environment == "dev":
        app.add_middleware(
            CORSMiddleware,
            allow_origins=[settings.cors_dev_origin],
            allow_methods=["GET", "POST", "DELETE"],
            allow_headers=["Authorization", "Content-Type"],
            allow_credentials=False,
        )
    app.add_middleware(SecurityMiddleware, state=app.state)
    return app


def create_app_prod():
    return create_app(Settings())


def main():
    import uvicorn

    uvicorn.run(
        "glyphlab_service.app:create_app_prod",
        factory=True,
        host="0.0.0.0",  # noqa: S104  # nosec B104 - Required container listener behind proxy
        port=8080,
        workers=1,
        access_log=False,
        proxy_headers=False,
    )

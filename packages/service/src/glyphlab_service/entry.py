"""Container entrypoint: migrate explicitly, then run exactly one web process."""

from .db.migrate import upgrade
from .settings import Settings


def main():
    import uvicorn

    settings = Settings()
    upgrade(settings)
    uvicorn.run(
        "glyphlab_service.app:create_app_prod",
        factory=True,
        host="0.0.0.0",  # noqa: S104  # nosec B104 - Required container listener behind proxy
        port=8080,
        workers=1,
        access_log=False,
        proxy_headers=False,
    )


if __name__ == "__main__":
    main()

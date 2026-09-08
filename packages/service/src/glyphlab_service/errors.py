import logging

from fastapi.exceptions import RequestValidationError
from glyphlab.errors import ERROR_REGISTRY, GlyphlabError
from starlette.exceptions import HTTPException
from starlette.responses import JSONResponse


def envelope(code, detail=None):
    entry = ERROR_REGISTRY[code]
    return {"error": {"code": code, "message": entry.message, "detail": detail or {}}}


def error_response(code, status=None, detail=None, headers=None):
    return JSONResponse(
        envelope(code, detail),
        status_code=status or ERROR_REGISTRY[code].http_status,
        headers=headers,
    )


def install_error_handlers(app):
    @app.exception_handler(GlyphlabError)
    async def domain_error(request, exc):
        return error_response(exc.code, detail=exc.detail)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        # Never echo raw invalid values (they may contain a token or private text).
        return error_response(
            "E_VALIDATION",
            detail={
                "fields": [{"location": list(e["loc"]), "type": e["type"]} for e in exc.errors()]
            },
        )

    @app.exception_handler(HTTPException)
    async def http_error(request, exc):
        return error_response(
            "E_NOT_FOUND" if exc.status_code == 404 else "E_VALIDATION",
            status=422 if exc.status_code == 400 else exc.status_code,
        )

    @app.exception_handler(Exception)
    async def unexpected_error(request, exc):
        logging.getLogger("glyphlab_service").error(
            "Unhandled request error", extra={"error_code": "E_INTERNAL"}
        )
        return error_response("E_INTERNAL")

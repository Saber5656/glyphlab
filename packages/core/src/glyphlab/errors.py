"""Canonical errors shared by core, CLI and service."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ErrorSpec:
    code: str
    http_status: int
    cli_exit: int
    description: str

    @property
    def message(self) -> str:
        """Compatibility alias used by API envelopes."""
        return self.description


_ERRORS = (
    ("E_IMG_FORMAT", 415, 3, "Unsupported or unrecognized image format"),
    ("E_IMG_TOO_LARGE", 413, 3, "Image bytes or pixel count over cap"),
    ("E_REQUEST_TOO_LARGE", 413, 3, "Non-upload request body over cap"),
    ("E_IMG_DECODE", 422, 3, "Image failed to decode"),
    ("E_PAGE_NO_MARKERS", 422, 3, "Fewer than four fiducials of one page found"),
    ("E_PAGE_AMBIGUOUS", 422, 3, "Markers of two or more pages in one photo"),
    ("E_PAGE_UNKNOWN", 422, 3, "Page not in this project's template"),
    ("E_PAGE_WARPED", 422, 3, "Rectification quality gate failed"),
    ("E_PAGE_BLURRY", 422, 3, "Sharpness gate failed"),
    ("E_TEMPLATE_MISMATCH", 409, 3, "Scan template does not match project"),
    ("E_TRACE_UNAVAILABLE", 500, 3, "No vectorizer engine available"),
    ("E_TRACE_TIMEOUT", 500, 3, "Tracing exceeded its time limit"),
    ("E_GLYPH_SVG_INVALID", 422, 3, "Glyph SVG failed the restricted parser"),
    ("E_QA_FAILED", 422, 4, "Font QA gate failed"),
    ("E_NOT_FOUND", 404, 3, "Unknown resource or bad token"),
    ("E_RATE_LIMITED", 429, 3, "Rate or queue limit hit"),
    ("E_QUOTA_EXCEEDED", 409, 3, "Project or global quota exceeded (global variant uses HTTP 507)"),
    ("E_JOB_LOST", 500, 1, "Job lease expired past retry budget"),
    ("E_BUILD_IN_PROGRESS", 409, 3, "A build job is already queued or running"),
    ("E_VALIDATION", 422, 3, "Input validation failed"),
    ("E_INTERNAL", 500, 1, "Unexpected error"),
)
ERROR_REGISTRY: dict[str, ErrorSpec] = {
    code: ErrorSpec(code, http, cli, desc) for code, http, cli, desc in _ERRORS
}


class GlyphlabError(Exception):
    """Base for errors that cross a core/API boundary."""

    code = "E_INTERNAL"

    def __init__(
        self,
        code_or_message: str,
        message: str | None = None,
        detail: dict[str, object] | None = None,
    ) -> None:
        if message is None:
            code = self.code
            text = code_or_message
        else:
            code = code_or_message
            text = message
        if code not in ERROR_REGISTRY:
            raise ValueError(f"unknown glyphlab error code: {code}")
        self.code = code
        self.message = text
        self.detail = detail
        super().__init__(text)


class GlyphSvgInvalidError(GlyphlabError):
    code = "E_GLYPH_SVG_INVALID"


class ConfigError(GlyphlabError):
    code = "E_VALIDATION"


def to_glyphlab_error(exc: Exception) -> GlyphlabError:
    from glyphlab.charset import UnknownCharsetError

    if isinstance(exc, GlyphlabError):
        return exc
    if isinstance(exc, UnknownCharsetError):
        return ConfigError(str(exc))
    return GlyphlabError(str(exc))

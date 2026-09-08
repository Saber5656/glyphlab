import pytest
from glyphlab.charset import UnknownCharsetError
from glyphlab.errors import (
    ERROR_REGISTRY,
    GlyphlabError,
    GlyphSvgInvalidError,
    to_glyphlab_error,
)


def test_registry_has_canonical_codes() -> None:
    assert set(ERROR_REGISTRY) == {
        "E_IMG_FORMAT",
        "E_IMG_TOO_LARGE",
        "E_REQUEST_TOO_LARGE",
        "E_IMG_DECODE",
        "E_PAGE_NO_MARKERS",
        "E_PAGE_AMBIGUOUS",
        "E_PAGE_UNKNOWN",
        "E_PAGE_WARPED",
        "E_PAGE_BLURRY",
        "E_TEMPLATE_MISMATCH",
        "E_TRACE_UNAVAILABLE",
        "E_TRACE_TIMEOUT",
        "E_GLYPH_SVG_INVALID",
        "E_QA_FAILED",
        "E_NOT_FOUND",
        "E_RATE_LIMITED",
        "E_QUOTA_EXCEEDED",
        "E_JOB_LOST",
        "E_BUILD_IN_PROGRESS",
        "E_VALIDATION",
        "E_INTERNAL",
    }
    assert ERROR_REGISTRY["E_QA_FAILED"].http_status == 422
    assert ERROR_REGISTRY["E_QA_FAILED"].cli_exit == 4


def test_error_and_mapping() -> None:
    error = GlyphSvgInvalidError("bad SVG", detail={"reason": "script"})
    assert error.code == "E_GLYPH_SVG_INVALID"
    assert error.detail == {"reason": "script"}
    assert to_glyphlab_error(UnknownCharsetError("bad")).code == "E_VALIDATION"
    with pytest.raises(GlyphlabError):
        raise error

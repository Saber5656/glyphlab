import json
import logging

from glyphlab_service.logging import JSONFormatter


def test_redaction():
    record = logging.LogRecord(
        "test",
        20,
        "",
        0,
        "%s",
        (
            {
                "Authorization": "secret",
                "nested": {"filename": "private.jpg", "token": "glp_hidden"},
                "count": 3,
            },
        ),
        None,
    )
    line = JSONFormatter().format(record)
    assert "private.jpg" not in line and "glp_" not in line and "secret" not in line
    assert json.loads(line)["level"] == "INFO"


def test_request_id_and_unexpected(client, app):
    @app.get("/api/test-error")
    def unexpected():
        raise RuntimeError("/private/secret/path")

    response = client.get("/api/test-error", headers={"X-Request-Id": "valid-id"})
    assert response.status_code == 500
    assert response.headers["x-request-id"] == "valid-id"
    assert response.json()["error"]["code"] == "E_INTERNAL"
    assert "/private/" not in response.text and "Traceback" not in response.text
    for key in [
        "x-content-type-options",
        "referrer-policy",
        "permissions-policy",
        "cross-origin-opener-policy",
        "cross-origin-resource-policy",
        "content-security-policy",
    ]:
        assert key in response.headers

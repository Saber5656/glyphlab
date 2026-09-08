"""ABUSE_BASE_URL runs the HTTP-only subset against a real container."""

import os

import httpx
import pytest
from fastapi.testclient import TestClient


def pytest_collection_modifyitems(items):
    if not os.environ.get("ABUSE_BASE_URL"):
        return
    for item in items:
        if "/abuse/" not in str(item.path):
            continue
        if any(
            name in item.fixturenames for name in ["app", "monkeypatch", "caplog"]
        ) or item.name in ["test_t5_timeout_boundary", "test_t10_t11_repo_guards"]:
            item.add_marker(pytest.mark.skip(reason="requires_inprocess"))


@pytest.fixture
def client(request):
    base = os.environ.get("ABUSE_BASE_URL")
    if base:
        # A unique synthetic IP only affects deployments explicitly configured to trust a proxy.
        with httpx.Client(base_url=base, timeout=160) as result:
            yield result
    else:
        app = request.getfixturevalue("app")
        with TestClient(app, raise_server_exceptions=False) as result:
            yield result

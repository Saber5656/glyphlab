import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[2] / "core" / "tests"))

import pytest
from fastapi.testclient import TestClient

from glyphlab_service.db.migrate import upgrade
from glyphlab_service.settings import Settings


@pytest.fixture
def app(tmp_path):
    from glyphlab_service.app import create_app

    settings = Settings(
        data_dir=tmp_path,
        environment="dev",
        rl_create_per_minute=10000,
        rl_create_per_day=10000,
        rl_default_per_minute=10000,
        rl_uploads_per_hour_ip=10000,
        rl_uploads_per_hour_project=10000,
        rl_builds_per_hour_project=10000,
    )
    upgrade(settings)
    result = create_app(settings, start_background=False)
    yield result
    result.state.engine.dispose()


@pytest.fixture
def client(app):
    with TestClient(app, raise_server_exceptions=False) as result:
        yield result


@pytest.fixture
def project(client):
    response = client.post(
        "/api/projects", json={"name": "テスト", "family_name": "TestFont", "charset_id": "ascii"}
    )
    assert response.status_code == 201, response.text
    return response.json()


def auth(project):
    return {"Authorization": "Bearer " + project["token"]}

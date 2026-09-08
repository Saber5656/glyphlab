"""Pinned OpenAPI and property-generated API calls through real ASGI transport."""

import json
from pathlib import Path

import pytest
import schemathesis
from hypothesis import HealthCheck, given, settings

from glyphlab_service.export_openapi import export_spec

EXPECTED = {
    "create_project",
    "get_project",
    "delete_project",
    "get_template_pdf",
    "create_upload",
    "get_job",
    "list_glyphs",
    "get_glyph_svg",
    "review_glyphs",
    "create_build",
    "list_artifacts",
    "download_artifact",
    "get_meta",
    "healthz",
}
PUBLIC = {"create_project", "get_meta", "healthz"}


def test_contract_pin_and_hygiene():
    spec = export_spec()
    assert spec == json.loads((Path(__file__).parents[1] / "openapi.json").read_text())
    operations = []
    for path, path_item in spec["paths"].items():
        assert path.startswith("/api/") or path == "/healthz"
        for operation in path_item.values():
            operations.append(operation)
            assert operation["operationId"]
            assert not any("token" in p["name"] for p in operation.get("parameters", []))
            if operation["operationId"] not in PUBLIC:
                assert operation["security"] == [{"bearerAuth": []}]
    assert {o["operationId"] for o in operations} == EXPECTED
    assert all("500" in o["responses"] for o in operations)


@pytest.mark.parametrize("operation_id", sorted(EXPECTED))
def test_schemathesis_raw_cases(app, operation_id):
    schema = schemathesis.openapi.from_asgi("/api/openapi.json", app)
    operation = next(
        result.ok()
        for result in schema.get_all_operations()
        if result.ok().definition.raw["operationId"] == operation_id
    )

    @settings(max_examples=50, deadline=None, suppress_health_check=list(HealthCheck))
    @given(operation.as_strategy())
    def run(case):
        case.headers = {}
        response = case.call()
        assert response.status_code < 500
        if operation_id not in PUBLIC:
            assert response.status_code == 404
            assert response.json()["error"]["code"] == "E_NOT_FOUND"
        else:
            case.validate_response(response)

    run()


def test_schemathesis_authenticated_cases(app, client, project, tmp_path):
    """Known-good project/glyph/job/artifact IDs allow property checks behind auth."""
    from schemathesis.checks import not_a_server_error
    from schemathesis.specs.openapi.checks import (
        response_schema_conformance,
        status_code_conformance,
    )
    from service_test_support import auth, process_next, scan_for_project

    path = "/api/projects/" + project["project_id"]
    scan = scan_for_project(client, app, project, tmp_path)
    client.post(
        path + "/uploads", headers=auth(project), files={"file": ("scan.png", scan, "image/png")}
    )
    ingest = process_next(app)
    assert ingest.status == "succeeded"
    client.post(path + "/builds", headers=auth(project), json={})
    build = process_next(app)
    assert build.status == "succeeded"
    artifact = client.get(path + "/artifacts", headers=auth(project)).json()["artifacts"][0]["id"]
    cp = client.get(path + "/glyphs?status=auto", headers=auth(project)).json()["glyphs"][0][
        "codepoint"
    ]
    schema = schemathesis.openapi.from_asgi("/api/openapi.json", app)
    operations = [result.ok() for result in schema.get_all_operations()]
    operations.sort(key=lambda op: op.definition.raw["operationId"] == "delete_project")
    for operation in operations:
        if operation.definition.raw["operationId"] in PUBLIC:
            continue

        @settings(max_examples=50, deadline=None, suppress_health_check=list(HealthCheck))
        @given(operation.as_strategy())
        def run(case):
            params = {
                "project_id": project["project_id"],
                "job_id": build.id,
                "artifact_id": artifact,
                "cp": cp,
            }
            case.path_parameters = {key: params[key] for key in (case.path_parameters or {})}
            case.headers = auth(project)
            response = case.call()
            assert response.status_code < 500
            case.validate_response(
                response,
                checks=[not_a_server_error, response_schema_conformance, status_code_conformance],
            )

        run()

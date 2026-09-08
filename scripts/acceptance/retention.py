"""Observe retention through HTTP and the bind mount, never through DB mutation."""

import json
import time
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

RETENTION_DAYS = 0.001
SWEEP_SECONDS = 5


def check_retention(base_url: str, data_dir: Path, *, timeout: float = 150) -> dict[str, object]:
    if urlparse(base_url).scheme not in ("http", "https"):
        raise ValueError("Retention endpoint must use HTTP(S)")

    def request(path: str, method="GET", body=None, token=None):
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = "Bearer " + token
        req = Request(  # noqa: S310 -- HTTP(S) endpoint validated above
            base_url + path,
            data=json.dumps(body).encode() if body is not None else None,
            headers=headers,
            method=method,
        )
        try:
            with urlopen(req, timeout=30) as response:  # noqa: S310 -- HTTP(S) only
                return response.status, response.read()
        except HTTPError as error:
            return error.code, error.read()

    started = time.monotonic()
    status, body = request(
        "/api/projects",
        "POST",
        {
            "name": "Retention acceptance",
            "family_name": "Retention Acceptance",
            "charset_id": "ascii",
        },
    )
    if status != 201:
        raise RuntimeError("Retention fixture project could not be created")
    project = json.loads(body)
    path = "/api/projects/" + project["project_id"]
    token = project["token"]
    status, pdf = request(path + "/template.pdf", token=token)
    if status != 200 or not pdf.startswith(b"%PDF"):
        raise RuntimeError("Retention fixture template failed")
    prefix = data_dir / "store/projects" / project["project_id"]
    if not prefix.is_dir():
        raise RuntimeError("Retention fixture store prefix was not created")
    if request(path, token=token)[0] != 200:
        raise RuntimeError("Retention fixture expired before observation")
    # Poll the canonical API across TTL plus a sweep. No timestamps or DB rows are edited.
    deadline = started + timeout
    observed_404 = None
    while time.monotonic() < deadline:
        status, _ = request(path, token=token)
        if status == 404 and not prefix.exists():
            observed_404 = time.monotonic() - started
            break
        if status not in (200, 404):
            raise RuntimeError(f"Retention lookup returned HTTP {status}")
        time.sleep(2)
    if observed_404 is None:
        raise RuntimeError(
            "Retention did not remove both API project and store prefix before deadline"
        )
    if observed_404 < RETENTION_DAYS * 86400 - 3:
        raise RuntimeError("Project disappeared before the configured nonzero TTL")
    return {
        "retention_days": RETENTION_DAYS,
        "sweep_interval_s": SWEEP_SECONDS,
        "observed_purge_s": round(observed_404, 3),
        "project_id": project["project_id"],
        "api_status": 404,
        "store_prefix_removed": True,
    }

"""Picklable process boundary: bytes/config only, never sessions or store clients."""

from dataclasses import dataclass, field


@dataclass
class IngestRequest:
    upload_bytes: bytes
    sidecar_json: bytes
    charset_id: str
    status_snapshot: dict[int, str]


@dataclass
class BuildRequest:
    svgs: dict[int, bytes]
    family_name: str
    version: int
    charset_id: str
    project_name: str = ""
    statuses: dict[int, str] = field(default_factory=dict)
    warnings: dict[int, list] = field(default_factory=dict)


@dataclass
class IngestResult:
    report: dict
    svgs: dict[int, bytes]
    metadata: dict[int, dict] = field(default_factory=dict)


@dataclass
class BuildResult:
    ttf: bytes
    woff2: bytes
    proof_html: bytes
    qa_json: bytes
    qa_passed: bool


@dataclass
class ChildError:
    code: str
    detail: dict = field(default_factory=dict)


ChildRequest = IngestRequest | BuildRequest
ChildResult = IngestResult | BuildResult | ChildError

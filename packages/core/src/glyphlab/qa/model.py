"""Stable QA report types shared by CLI and service."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal


@dataclass(frozen=True)
class QAFinding:
    check_id: str
    severity: Literal["FAIL", "WARN", "SKIPPED", "ALLOWED"]
    message: str
    detail: dict[str, object] | None = None


@dataclass(frozen=True)
class ExpectedBuild:
    codepoints: set[int]
    advances: dict[int, int]


@dataclass(frozen=True)
class QAReport:
    passed: bool
    findings: list[QAFinding]

    def write(self, path: Path) -> None:
        path.write_text(
            json.dumps(
                {"schema": "glyphlab.qa-report/1", **asdict(self)}, indent=2, ensure_ascii=False
            )
            + "\n",
            encoding="utf-8",
        )

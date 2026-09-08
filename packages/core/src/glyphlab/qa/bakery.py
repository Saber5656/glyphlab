"""Bounded, shell-free execution of Font Bakery's universal profile."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
import tomllib
from pathlib import Path
from typing import Literal, cast

from glyphlab.qa.model import QAFinding


def load_allowlist(path: Path | None = None) -> dict[str, str]:
    source = path or Path(__file__).with_name("allowlist.toml")
    data = tomllib.loads(source.read_text(encoding="utf-8"))
    allowed: dict[str, str] = {}
    for entry in data.get("allow", []):
        if not entry.get("reason", "").strip():
            raise ValueError("Every QA allowlist entry requires a reason")
        allowed[entry["check"]] = entry["reason"]
    return allowed


def parse_bakery_report(data: object, allowed: dict[str, str]) -> list[QAFinding]:
    """Parse Font Bakery 1.1's nested sections/checks/logs report."""
    findings: list[QAFinding] = []

    def visit(node: object, check_id: str = "fontbakery") -> None:
        if isinstance(node, list):
            for entry in node:
                visit(entry, check_id)
        elif isinstance(node, dict):
            key = node.get("key")
            if isinstance(key, dict):
                check_id = str(key.get("check", check_id))
            elif isinstance(key, (list, tuple)) and len(key) > 1 and isinstance(key[1], str):
                check_id = key[1]
            elif isinstance(key, str):
                check_id = key
            if "check" in node and isinstance(node["check"], str):
                check_id = node["check"]
            match = re.fullmatch(r"<FontBakeryCheck:(.+)>", check_id)
            if match:
                check_id = match[1]
            status = node.get("status")
            if status in ("FAIL", "ERROR", "WARN"):
                severity = "FAIL" if status in ("FAIL", "ERROR") else "WARN"
                detail: dict[str, object] | None = None
                if check_id in allowed:
                    severity = "ALLOWED"
                    detail = {"reason": allowed[check_id]}
                findings.append(
                    QAFinding(
                        check_id,
                        cast(Literal["FAIL", "WARN", "ALLOWED"], severity),
                        str(node["message"].get("message", status))
                        if isinstance(node.get("message"), dict)
                        else str(node.get("message", status)),
                        detail,
                    )
                )
            for field in ("sections", "checks", "logs", "results"):
                if field in node:
                    visit(node[field], check_id)

    visit(data)
    return findings


def run_fontbakery(ttf_path: Path, *, require_bakery: bool) -> list[QAFinding]:
    binary = shutil.which("fontbakery")
    if binary is None:
        return [
            QAFinding(
                "fontbakery/unavailable",
                "FAIL" if require_bakery else "SKIPPED",
                "Install glyphlab[qa] to run Font Bakery",
            )
        ]
    # An explicit skip bypasses bakery even if installed, but never structural QA.
    if not require_bakery:
        return [QAFinding("fontbakery/skipped", "SKIPPED", "Font Bakery skipped explicitly")]
    try:
        with tempfile.TemporaryDirectory(prefix="glyphlab-qa-") as temp:
            output = Path(temp) / "report.json"
            result = subprocess.run(  # noqa: S603 - argv uses a resolved executable, never a shell
                [
                    binary,
                    "check-universal",
                    "--json",
                    str(output),
                    "--no-progress",
                    "--skip-network",
                    "--loglevel",
                    "WARN",
                    str(ttf_path.resolve()),
                ],
                capture_output=True,
                text=True,
                timeout=120,
                check=False,
            )
            if not output.is_file():
                return [
                    QAFinding(
                        "fontbakery/execution",
                        "FAIL",
                        f"Font Bakery produced no report (exit {result.returncode})",
                    )
                ]
            raw = json.loads(output.read_text(encoding="utf-8"))
            if not isinstance(raw, dict) or not any(
                k in raw for k in ("sections", "checks", "results")
            ):
                return [QAFinding("fontbakery/report", "FAIL", "Unrecognized Font Bakery report")]
            findings = parse_bakery_report(raw, load_allowlist())
            if result.returncode not in (0, 1) and not any(f.severity == "FAIL" for f in findings):
                findings.append(
                    QAFinding(
                        "fontbakery/execution", "FAIL", f"Font Bakery exited {result.returncode}"
                    )
                )
            return findings
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        return [QAFinding("fontbakery/execution", "FAIL", str(exc))]

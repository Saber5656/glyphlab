"""Evidence aggregation that never labels missing or skipped checks as accepted."""

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

from defusedxml import ElementTree


@dataclass(frozen=True)
class Evidence:
    item: str
    design_ref: str
    result: str
    evidence: str
    measurement: str = ""


@dataclass
class AcceptanceRun:
    tested_commit: str
    started_at: str
    rows: list[Evidence] = field(default_factory=list)

    required_items = frozenset(
        {
            "cli-clean-scan",
            "cli-phone-tilt",
            "hosted",
            "retention",
            "performance-template",
            "performance-ingest",
            "performance-build",
            "performance-memory",
            "container-hardening",
            "workflow-hygiene",
            "python-audit",
            "npm-audit",
            "gitleaks-main",
            "dependabot",
            *(f"T{i}" for i in range(1, 13)),
        }
    )

    def validate(self) -> None:
        if not re.fullmatch(r"[0-9a-f]{40}", self.tested_commit):
            raise ValueError("A complete immutable tested commit is required")
        items = {row.item for row in self.rows}
        if self.required_items - items:
            raise ValueError("Missing evidence: " + ", ".join(sorted(self.required_items - items)))
        if any(row.result != "pass" for row in self.rows):
            raise ValueError("An acceptance report requires every recorded check to pass")
        if len(items) != len(self.rows):
            raise ValueError("Duplicate evidence rows")

    def save_evidence(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(self), sort_keys=True, indent=2) + "\n")

    def write_report(self, path: Path) -> None:
        self.validate()
        text = [
            "# Product acceptance evidence",
            "",
            f"Tested commit: `{self.tested_commit}`",
            f"Run started (UTC): {self.started_at}",
            "",
            "This report records the immutable commit executed. A later report-only commit",
            "may add this document without changing the tested implementation; it does not change",
            "the tested commit to the report commit. Any implementation change requires a new run.",
            "",
            "| Item | DESIGN reference | Result | Evidence | Measurement |",
            "|---|---|---|---|---|",
        ]
        for row in sorted(self.rows, key=lambda row: row.item):
            cells = [row.item, row.design_ref, row.result, row.evidence, row.measurement]
            text.append(
                "| " + " | ".join(c.replace("|", "\\|").replace("\n", " ") for c in cells) + " |"
            )
        text.extend(
            [
                "",
                "## Release checklist (human decision)",
                "",
                "- [ ] Version bump",
                "- [ ] Release tag",
                "- [ ] TestPyPI dry run",
                "- [ ] PyPI approval",
                "- [ ] First production deployment decision",
                "- [ ] Announcement",
                "",
                "These results use synthetic handwriting. Physical printing, real handwriting,",
                "and real phone photographs remain outside this acceptance run.",
                "",
            ]
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".md.tmp")
        temporary.write_text("\n".join(text))
        temporary.replace(path)


def memory_bytes(value: str) -> int:
    match = re.fullmatch(r"\s*([\d.]+)\s*(B|kB|MB|GB|KiB|MiB|GiB)\s*(?:/.*)?", value)
    if not match:
        raise ValueError("Unrecognized docker memory measurement")
    factors = {
        "B": 1,
        "kB": 1000,
        "MB": 1000**2,
        "GB": 1000**3,
        "KiB": 2**10,
        "MiB": 2**20,
        "GiB": 2**30,
    }
    return int(float(match[1]) * factors[match[2]])


def parse_junit(path: Path) -> dict[str, str]:
    root = ElementTree.parse(path).getroot()
    result = {}
    for case in root.iter("testcase"):
        state = (
            "fail"
            if case.find("failure") is not None or case.find("error") is not None
            else ("skipped" if case.find("skipped") is not None else "pass")
        )
        result[case.attrib["name"]] = state
    return result

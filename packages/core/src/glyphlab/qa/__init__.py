"""Font QA gate shared by both product surfaces."""

from pathlib import Path

from glyphlab.charset.model import CharsetSpec
from glyphlab.qa.bakery import run_fontbakery
from glyphlab.qa.model import ExpectedBuild, QAFinding, QAReport
from glyphlab.qa.structural import run_structural_checks

__all__ = ["ExpectedBuild", "QAFinding", "QAReport", "run_qa"]


def run_qa(
    ttf: Path, charset: CharsetSpec, expected: ExpectedBuild, *, require_bakery: bool
) -> QAReport:
    findings = run_structural_checks(ttf, charset, expected)
    findings += run_fontbakery(ttf, require_bakery=require_bakery)
    findings.sort(key=lambda finding: finding.check_id)
    report = QAReport(not any(f.severity == "FAIL" for f in findings), findings)
    report.write(ttf.parent / "qa-report.json")
    return report

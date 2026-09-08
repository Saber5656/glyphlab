import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[4]))
from scripts.acceptance.model import AcceptanceRun, Evidence, memory_bytes, parse_junit


def test_docker_memory_units_and_limits():
    assert memory_bytes("127.5MiB / 1GiB") == int(127.5 * 2**20)
    assert memory_bytes("1.25GiB / 8GiB") == int(1.25 * 2**30)
    assert memory_bytes("512kB / 2GB") == 512000
    with pytest.raises(ValueError):
        memory_bytes("not available")


def test_incomplete_run_cannot_replace_accepted_report(tmp_path):
    report = tmp_path / "ACCEPTANCE.md"
    report.write_text("previous accepted result")
    run = AcceptanceRun("a" * 40, "2026-09-08T00:00:00Z")
    run.rows.append(Evidence("cli-clean-scan", "18.3", "pass", "cli.log"))
    with pytest.raises(ValueError, match="Missing evidence"):
        run.write_report(report)
    assert report.read_text() == "previous accepted result"


def test_report_pins_tested_commit_and_has_human_release_checklist(tmp_path):
    run = AcceptanceRun("a" * 40, "2026-09-08T00:00:00Z")
    for item in run.required_items:
        run.rows.append(Evidence(item, "18.3", "pass", "work/acceptance/log.txt"))
    report = tmp_path / "ACCEPTANCE.md"
    run.write_report(report)
    text = report.read_text()
    assert "Tested commit: `" + ("a" * 40) + "`" in text
    assert "report-only commit" in text and "- [ ] PyPI approval" in text


def test_junit_never_counts_skipped_attacks_as_passed(tmp_path):
    report = tmp_path / "junit.xml"
    report.write_text(
        '<testsuites><testsuite><testcase name="test_t1_bomb"/>'
        '<testcase name="test_t9_egress"><skipped/></testcase>'
        '<testcase name="test_t2_tokens"><failure/></testcase></testsuite></testsuites>'
    )
    assert parse_junit(report) == {
        "test_t1_bomb": "pass",
        "test_t9_egress": "skipped",
        "test_t2_tokens": "fail",
    }


def test_subprocess_logs_redact_project_tokens(tmp_path):
    from scripts.acceptance.common import run_command

    output, _ = run_command(
        [sys.executable, "-c", "print('glp_' + 'a' * 43)"],
        log=tmp_path / "command.log",
        cwd=tmp_path,
    )
    assert "glp_" in output
    assert "glp_" not in (tmp_path / "command.log").read_text()
    assert "[redacted]" in (tmp_path / "command.log").read_text()


def test_acceptance_command_timeout_is_bounded(tmp_path):
    from scripts.acceptance.common import run_command

    with pytest.raises(RuntimeError, match="exceeded"):
        run_command(
            [sys.executable, "-c", "import time; time.sleep(5)"],
            log=tmp_path / "timeout.log",
            cwd=tmp_path,
            timeout=0.1,
        )
    assert "timed out" in (tmp_path / "timeout.log").read_text()

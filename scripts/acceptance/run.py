"""One-command product acceptance with honest partial-run evidence."""

# ruff: noqa: S603, S607 -- fixed tool names, argv lists and task-owned output paths
import argparse
import json
import os
import subprocess
import threading
import time
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import urlopen

from .common import run_command, sha256
from .model import AcceptanceRun, Evidence, memory_bytes, parse_junit
from .retention import RETENTION_DAYS, SWEEP_SECONDS, check_retention

ROOT = Path(__file__).resolve().parents[2]


class Runner:
    def __init__(self, args):
        self.args = args
        self.commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip()
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        self.output = (
            args.output or ROOT / "work/acceptance" / f"{stamp}-{self.commit[:8]}"
        ).resolve()
        self.output.mkdir(parents=True, exist_ok=False)
        self.evidence = AcceptanceRun(self.commit, datetime.now(UTC).isoformat())
        self.project = args.compose_project or f"glyphlab-acceptance-{self.commit[:8]}"
        self.env = os.environ.copy()
        self.env["SOURCE_DATE_EPOCH"] = "1700000000"
        self.compose = [
            "docker",
            "compose",
            "-p",
            self.project,
            "-f",
            "deploy/docker-compose.yml",
            "-f",
            "deploy/compose.e2e.yml",
        ]

    def logref(self, name):
        path = self.output / name
        try:
            return str(path.relative_to(ROOT))
        except ValueError:
            return path.name

    def run(self, name, argv, *, cwd=ROOT, env=None, timeout=1800):
        print(f"[acceptance] {name}", flush=True)
        return run_command(
            argv, log=self.output / f"{name}.log", cwd=cwd, env=env or self.env, timeout=timeout
        )

    def record(self, item, ref, log, measurement=""):
        self.evidence.rows.append(Evidence(item, ref, "pass", self.logref(log), measurement))
        self.evidence.save_evidence(self.output / "evidence.json")

    def cli(self):
        dist = self.output / "dist"
        self.run("wheel-build", ["uv", "build", "--package", "glyphlab", "--out-dir", str(dist)])
        wheels = list(dist.glob("glyphlab-*.whl"))
        if len(wheels) != 1:
            raise RuntimeError("Acceptance requires exactly one newly built core wheel")
        wheel = wheels[0]
        venv = self.output / "wheel-venv"
        self.run("wheel-venv", ["uv", "venv", "--python", "3.12", str(venv)])
        python = venv / "bin/python"
        self.run(
            "wheel-install",
            ["uv", "pip", "install", "--python", str(python), f"{wheel}[trace,qa]", "pypdfium2"],
        )
        env = self.env.copy()
        env.pop("PYTHONPATH", None)
        env.pop("PYTHONHOME", None)
        cli_output = self.output / "cli"
        self.run(
            "wheel-journeys",
            [
                str(python),
                "-I",
                str(ROOT / "scripts/acceptance/cli_wheel.py"),
                "--repo",
                str(ROOT),
                "--output",
                str(cli_output),
            ],
            cwd=self.output,
            env=env,
        )
        result = json.loads((cli_output / "result.json").read_text())
        if not result["isolated_mode"]:
            raise RuntimeError("Wheel runner did not use isolated Python")
        result["wheel_sha256"] = sha256(wheel)
        (self.output / "wheel-result.json").write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n"
        )
        for profile in result["profiles"]:
            self.record(
                "cli-" + profile["profile"],
                "18.3 / 20",
                "wheel-result.json",
                f"{profile['pages']} pages; {profile['encoded']} encoded; "
                f"wheel sha256 {result['wheel_sha256']}",
            )
        for name, key, budget in [
            ("template", "template_s", 5),
            ("ingest", "ingest_s_per_page", 15),
            ("build", "build_s", 10),
        ]:
            measured = max(profile["timings"][key] for profile in result["profiles"])
            self.record(
                "performance-" + name,
                "21",
                "wheel-result.json",
                f"{measured:.3f} s; budget {budget}s; gate {budget * 1.5}s",
            )

    def health(self, base):
        if urlparse(base).scheme not in ("http", "https"):
            raise ValueError("Acceptance endpoints must use HTTP(S)")
        deadline = time.monotonic() + 120
        while time.monotonic() < deadline:
            try:
                with urlopen(base + "/healthz", timeout=3) as response:  # noqa: S310 -- scheme validated above
                    if response.status == 200:
                        return
            except OSError:
                pass
            time.sleep(1)
        raise RuntimeError("Compose health check did not become ready")

    def hosted(self):
        started = False
        try:
            if self.args.stack_mode == "manage":
                data = self.args.data_dir.resolve()
                if not data.exists():
                    data.mkdir()
                    data.chmod(0o777)  # dedicated synthetic-test bind mount
                self.run(
                    "compose-up", self.compose + ["up", "-d", "--build", "--wait"], timeout=1800
                )
                started = True
            self.health(self.args.base_url)
            cid, _ = self.run("compose-container", self.compose + ["ps", "-q", "app"])
            cid = cid.strip()
            if not cid:
                raise RuntimeError("Compose app container ID is unavailable")
            info, _ = self.run("container-inspect", ["docker", "inspect", cid])
            container = json.loads(info)[0]
            user = container["Config"].get("User", "")
            readonly = container["HostConfig"].get("ReadonlyRootfs", False)
            if user.split(":", 1)[0] in ("", "0", "root") or not readonly:
                raise RuntimeError(
                    "Container must run as non-root with a read-only root filesystem"
                )
            self.record(
                "container-hardening",
                "17.5",
                "container-inspect.log",
                f"user={user}; readonly={readonly}",
            )
            env = self.env.copy()
            env["E2E_BASE_URL"] = self.args.base_url
            env["PLAYWRIGHT_BASE_URL"] = self.args.base_url
            env["GLYPHLAB_E2E_DATA_DIR"] = str(self.args.data_dir.resolve())
            env["E2E_DATA_DIR"] = str(self.args.data_dir.resolve())
            sampling_started = time.monotonic()
            samples = []
            errors = []
            stop = threading.Event()

            def sample():
                while not stop.is_set():
                    try:
                        value = subprocess.check_output(
                            ["docker", "stats", "--no-stream", "--format", "{{.MemUsage}}", cid],
                            text=True,
                            timeout=10,
                        ).strip()
                        samples.append(
                            {
                                "elapsed_s": time.monotonic() - sampling_started,
                                "bytes": memory_bytes(value),
                                "raw": value,
                            }
                        )
                    except (OSError, subprocess.SubprocessError, ValueError) as exc:
                        errors.append(type(exc).__name__)
                    stop.wait(0.25)

            sampler = threading.Thread(target=sample, daemon=True)
            sampler.start()
            try:
                self.run(
                    "playwright",
                    ["npx", "playwright", "test"],
                    cwd=ROOT / "webui",
                    env=env,
                    timeout=900,
                )
            finally:
                stop.set()
                sampler.join(timeout=12)
                (self.output / "container-memory.json").write_text(
                    json.dumps({"samples": samples, "errors": errors}, indent=2) + "\n"
                )
            if not samples or errors:
                raise RuntimeError("Container memory sampling was incomplete")
            maximum = max(sample["bytes"] for sample in samples)
            if maximum <= 0 or maximum >= 800 * 2**20:
                raise RuntimeError("Container exceeded the hard 800 MiB memory ceiling")
            self.record(
                "hosted",
                "18.3 / 16",
                "playwright.log",
                "all configured Chromium, WebKit, mobile projects",
            )
            self.record(
                "performance-memory",
                "21",
                "container-memory.json",
                f"peak sampled {maximum / 2**20:.2f} MiB; ceiling <800 MiB",
            )
            self.run("compose-restart-before-abuse", self.compose + ["restart", "app"], timeout=120)
            self.health(self.args.base_url)
            self.abuse()
        finally:
            try:
                self.run("compose-logs", self.compose + ["logs", "--no-color"], timeout=60)
            except RuntimeError:
                pass
            if started:
                self.run("compose-down", self.compose + ["down"], timeout=120)

    def abuse(self):
        local_xml = self.output / "abuse-inprocess.xml"
        container_xml = self.output / "abuse-container.xml"
        local_env = self.env.copy()
        local_env.pop("ABUSE_BASE_URL", None)
        self.run(
            "abuse-inprocess",
            [
                "uv",
                "run",
                "pytest",
                "packages/service/tests/abuse",
                "-q",
                f"--junitxml={local_xml}",
            ],
            env=local_env,
            timeout=240,
        )
        container_env = self.env.copy()
        container_env["ABUSE_BASE_URL"] = self.args.base_url
        self.run(
            "abuse-container",
            [
                "uv",
                "run",
                "pytest",
                "packages/service/tests/abuse",
                "-q",
                f"--junitxml={container_xml}",
            ],
            env=container_env,
            timeout=240,
        )
        local = parse_junit(local_xml)
        container = parse_junit(container_xml)
        if not any(state == "pass" for state in container.values()):
            raise RuntimeError("No attacks executed in container mode")
        for i in range(1, 13):
            names = [
                name
                for name, state in local.items()
                if state == "pass" and (f"_t{i}_" in name or (i == 11 and "_t10_t11_" in name))
            ]
            if not names:
                raise RuntimeError(f"T{i} has no successful executable evidence")
            container_names = [name for name in names if container.get(name) == "pass"]
            self.record(
                f"T{i}",
                "17.3",
                "abuse-inprocess.log",
                f"in-process: {', '.join(names)}; "
                f"container: {', '.join(container_names) or 'requires_inprocess; skipped'}",
            )

    def retention(self):
        directory = self.output / "retention-data"
        directory.mkdir()
        directory.chmod(0o777)
        override = self.output / "retention.yml"
        override.write_text(
            "services:\n  app:\n    volumes:\n      - "
            + json.dumps(str(directory) + ":/data")
            + '\n    environment:\n      GLYPHLAB_RETENTION_DAYS: "0.001"\n'
            + '      GLYPHLAB_SWEEP_INTERVAL_S: "5"\n'
        )
        command = [
            "docker",
            "compose",
            "-p",
            self.project + "-retention",
            "-f",
            "deploy/docker-compose.yml",
            "-f",
            str(override),
        ]
        env = self.env.copy()
        env["GLYPHLAB_PORT"] = str(self.args.retention_port)
        try:
            self.run("retention-up", command + ["up", "-d", "--wait"], env=env, timeout=180)
            base = f"http://127.0.0.1:{self.args.retention_port}"
            self.health(base)
            result = check_retention(base, directory)
            (self.output / "retention.json").write_text(json.dumps(result, indent=2) + "\n")
            self.record(
                "retention",
                "14.4 / 18.3",
                "retention.json",
                f"TTL {RETENTION_DAYS} days; sweep {SWEEP_SECONDS}s; "
                f"purge observed at {result['observed_purge_s']}s",
            )
        finally:
            self.run("retention-logs", command + ["logs", "--no-color"], env=env, timeout=60)
            self.run("retention-down", command + ["down"], env=env, timeout=120)

    def security(self):
        self.run("workflow-hygiene", ["bash", "scripts/check_workflow_hygiene.sh"])
        self.record("workflow-hygiene", "17.3 T10/T11", "workflow-hygiene.log")
        requirements = self.output / "requirements.txt"
        self.run(
            "locked-dependencies",
            [
                "uv",
                "export",
                "--locked",
                "--all-packages",
                "--all-extras",
                "--no-emit-workspace",
                "--format",
                "requirements.txt",
                "-o",
                str(requirements),
            ],
        )
        ignores = []
        exceptions = ROOT / "security/pip-audit-ignores.txt"
        if exceptions.exists():
            for line in exceptions.read_text().splitlines():
                if line.strip() and not line.lstrip().startswith("#"):
                    ignores += ["--ignore-vuln", line.split()[0]]
        self.run(
            "python-audit",
            ["uvx", "pip-audit", "--strict", "-r", str(requirements), *ignores],
            timeout=900,
        )
        self.record(
            "python-audit",
            "17.3 T10",
            "python-audit.log",
            f"{len(ignores) // 2} explicitly listed repository exceptions",
        )
        self.run(
            "npm-audit",
            ["npm", "audit", "--omit=dev", "--audit-level=high"],
            cwd=ROOT / "webui",
            timeout=300,
        )
        self.record("npm-audit", "17.3 T10", "npm-audit.log")
        dependabot = ROOT / ".github/dependabot.yml"
        if not dependabot.is_file():
            raise RuntimeError("Dependabot configuration is missing")
        self.run(
            "dependabot-tracked", ["git", "ls-files", "--error-unmatch", ".github/dependabot.yml"]
        )
        self.record(
            "dependabot", "17.3 T10", "dependabot-tracked.log", f"sha256 {sha256(dependabot)}"
        )
        repo, _ = self.run("github-repository", ["gh", "repo", "view", "--json", "nameWithOwner"])
        repository = json.loads(repo)["nameWithOwner"]
        runs, _ = self.run(
            "gitleaks-main-run",
            [
                "gh",
                "api",
                f"repos/{repository}/actions/workflows/security.yml/runs?branch=main&per_page=1",
            ],
        )
        runs = json.loads(runs)["workflow_runs"]
        if not runs:
            raise RuntimeError(
                "No Security workflow run exists on main; acceptance remains incomplete"
            )
        latest = runs[0]
        jobs, _ = self.run(
            "gitleaks-main-jobs",
            ["gh", "api", f"repos/{repository}/actions/runs/{latest['id']}/jobs?per_page=100"],
        )
        matches = [job for job in json.loads(jobs)["jobs"] if job["name"] == "gitleaks-full"]
        if (
            latest["head_branch"] != "main"
            or len(matches) != 1
            or matches[0]["conclusion"] != "success"
        ):
            raise RuntimeError(
                "The latest main Security run has no successful full-history gitleaks job"
            )
        self.record(
            "gitleaks-main",
            "17.3 T11",
            "gitleaks-main-jobs.log",
            f"{matches[0]['html_url']} at {latest['head_sha']}",
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--only", choices=("all", "cli"), default="all")
    parser.add_argument("--stack-mode", choices=("manage", "existing"), default="manage")
    parser.add_argument("--compose-project")
    parser.add_argument("--base-url", default="http://127.0.0.1:8080")
    parser.add_argument("--retention-port", type=int, default=18081)
    parser.add_argument("--data-dir", type=Path, default=ROOT / "e2e-data")
    args = parser.parse_args()
    runner = Runner(args)
    try:
        if args.only == "all":
            dirty = subprocess.check_output(
                ["git", "status", "--porcelain", "--untracked-files=all"], cwd=ROOT, text=True
            )
            unexpected = [
                line
                for line in dirty.splitlines()
                if not line[3:].startswith(
                    ("work/", "e2e-data/", "webui/test-results/", "webui/playwright-report/")
                )
                and line[3:] != "docs/ACCEPTANCE.md"
            ]
            if unexpected:
                raise RuntimeError(
                    "Full acceptance requires committed implementation inputs; "
                    "commit changes or use --only cli for a partial tooling check"
                )
        runner.cli()
        if args.only == "cli":
            print(f"Partial CLI evidence saved to {runner.output}; no acceptance report written.")
            return
        runner.hosted()
        runner.retention()
        runner.security()
        current = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
        if current != runner.commit:
            raise RuntimeError("HEAD changed during acceptance; rerun against one immutable commit")
        runner.evidence.write_report(runner.output / "ACCEPTANCE.md")
        runner.evidence.write_report(ROOT / "docs/ACCEPTANCE.md")
        print(
            f"Acceptance passed for tested commit {runner.commit}; "
            "report written to docs/ACCEPTANCE.md"
        )
    except Exception as exc:
        runner.evidence.save_evidence(runner.output / "evidence.json")
        (runner.output / "FAILURE.txt").write_text(str(exc) + "\n")
        print(f"Acceptance incomplete: {exc}. Evidence: {runner.output}", flush=True)
        raise


if __name__ == "__main__":
    main()

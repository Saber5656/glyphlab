"""Bounded subprocess logging with token redaction and immutable artifact hashes."""

# ruff: noqa: S603 -- trusted argv lists assembled by checked-in acceptance tooling
import hashlib
import os
import re
import signal
import subprocess
import time
from pathlib import Path

TOKEN = re.compile(r"glp_[A-Za-z0-9_-]+")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run_command(
    argv: list[str],
    *,
    log: Path,
    cwd: Path,
    env: dict[str, str] | None = None,
    timeout: float = 1800,
) -> tuple[str, float]:
    log.parent.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    process = subprocess.Popen(
        argv,
        cwd=cwd,
        env=env or os.environ.copy(),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        start_new_session=True,
    )
    try:
        stdout, _ = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        # Kill the uv/pytest/CLI process group, including inherited pipe owners.
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        stdout, _ = process.communicate(timeout=10)
        log.write_text(TOKEN.sub("[redacted]", stdout) + "\nAcceptance command timed out.\n")
        raise RuntimeError(f"Command exceeded {timeout} seconds; see {log.name}") from exc
    result = subprocess.CompletedProcess(argv, process.returncode, stdout)
    output = TOKEN.sub("[redacted]", result.stdout)
    elapsed = time.monotonic() - started
    log.write_text(output + f"\n[acceptance] exit={result.returncode} elapsed_s={elapsed:.3f}\n")
    if result.returncode:
        raise RuntimeError(f"Command failed with exit {result.returncode}; see {log.name}")
    return result.stdout, elapsed

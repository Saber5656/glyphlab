"""CLI journeys executed entirely by a newly installed wheel's interpreter."""

# ruff: noqa: S603 -- fixed CLI/uv argv with task-owned paths, no shell
import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path


def worker(repo: Path, output: Path) -> None:
    import glyphlab

    installed = Path(glyphlab.__file__).resolve()
    if (
        not installed.is_relative_to(Path(sys.prefix).resolve())
        or "site-packages" not in installed.parts
    ):
        raise RuntimeError("Acceptance must import glyphlab from the isolated wheel environment")
    # Only fixture support is loaded from the checkout, never production src code.
    sys.path.insert(0, str(repo / "packages/core/tests"))
    from corpus.generate import generate_corpus
    from fontTools.ttLib import TTFont
    from glyphlab.template.sidecar import read_sidecar

    def sha256(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()

    executable = Path(sys.executable).with_name("glyphlab")
    env = os.environ.copy()
    env["SOURCE_DATE_EPOCH"] = "1700000000"
    env.pop("PYTHONPATH", None)
    env.pop("PYTHONHOME", None)
    env["PATH"] = str(executable.parent) + os.pathsep + env.get("PATH", "")
    output.mkdir(parents=True, exist_ok=True)

    def invoke(project: Path, label: str, *args: str):
        started = time.monotonic()
        result = subprocess.run(
            [str(executable), "--project", str(project), "--json", *args],
            cwd=output,
            env=env,
            capture_output=True,
            text=True,
            timeout=900,
            check=False,
        )
        elapsed = time.monotonic() - started
        (output / f"{label}.log").write_text(result.stdout + result.stderr)
        if result.returncode:
            raise RuntimeError(f"Installed CLI failed at {label}: exit {result.returncode}")
        return json.loads(result.stdout)["data"], elapsed

    results = []
    for profile in ("clean-scan", "phone-tilt"):
        project = output / profile
        invoke(
            project,
            f"{profile}-new",
            "new",
            "AcceptanceHand",
            "--family-name",
            "AcceptanceHand",
            "--dir",
            str(project),
        )
        template, template_s = invoke(project, f"{profile}-template", "template")
        sidecar = read_sidecar(Path(template["sidecar"]))
        manifests = generate_corpus(
            Path(template["pdf"]), sidecar, profile, None, 42, project / "scans"
        )
        expected = {
            int(cp[2:], 16) for path in manifests for cp in json.loads(path.read_text())["inked"]
        }
        ingest, ingest_s = invoke(project, f"{profile}-ingest", "ingest")
        if ingest["coverage"]["have"] != len(expected) or any(
            page["counts"]["failed"] for page in ingest["pages"]
        ):
            raise RuntimeError("Installed CLI ingest did not match the exact corpus manifest")
        invoke(project, f"{profile}-accept", "accept", "--all-auto")
        built, build_s = invoke(project, f"{profile}-build", "build")
        if not built["qa"]["passed"]:
            raise RuntimeError("Installed CLI font QA failed")
        with TTFont(built["ttf"]) as font:
            if set(font.getBestCmap()) != expected | {32, 0x3000}:
                raise RuntimeError("Built cmap differs from manifest")
            for cp, name in font.getBestCmap().items():
                if cp >= 0x3000 and font["hmtx"][name][0] != 1000:
                    raise RuntimeError("Japanese advance is not full width")
        original = Path(built["ttf"]).read_bytes()
        repeat, _ = invoke(project, f"{profile}-rebuild", "build")
        if Path(repeat["ttf"]).read_bytes() != original:
            raise RuntimeError("Repeated font build is not byte-stable")
        proof = Path(built["proof"]).read_text()
        if "Content-Security-Policy" not in proof or "data:font/woff2;base64," not in proof:
            raise RuntimeError("Installed proof sheet lacks CSP or embedded font")
        timings = {
            "template_s": template_s,
            "ingest_s_per_page": ingest_s / len(manifests),
            "build_s": build_s,
        }
        if template_s > 7.5 or timings["ingest_s_per_page"] > 22.5 or build_s > 15:
            raise RuntimeError(f"CLI timing exceeded 1.5 times DESIGN budget: {timings}")
        artifacts = {
            kind: {
                "path": str(Path(built[kind]).relative_to(output)),
                "sha256": sha256(Path(built[kind])),
            }
            for kind in ("ttf", "woff2", "proof")
        }
        results.append(
            {
                "profile": profile,
                "encoded": len(expected) + 2,
                "pages": len(manifests),
                "timings": timings,
                "artifacts": artifacts,
                "qa_passed": True,
            }
        )
    (output / "result.json").write_text(
        json.dumps(
            {
                "wheel_import": "site-packages/glyphlab",
                "isolated_mode": bool(sys.flags.isolated),
                "profiles": results,
            },
            sort_keys=True,
            indent=2,
        )
        + "\n"
    )
    print("Wheel-installed CLI acceptance passed: clean-scan and phone-tilt")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    worker(args.repo.resolve(), args.output.resolve())


if __name__ == "__main__":
    main()

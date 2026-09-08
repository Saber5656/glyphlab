"""Full local product acceptance: installed entry point, real scans, traces and Font Bakery."""

# ruff: noqa: S603, S607
# Fixed CLI names and test-owned temporary paths; subprocesses never use shell interpolation.
import json
import os
import subprocess
import time
from pathlib import Path

import pytest
from corpus.generate import generate_corpus
from fontTools.ttLib import TTFont
from glyphlab.cli.main import app
from glyphlab.project.store import ProjectStore
from glyphlab.template.sidecar import read_sidecar
from typer.testing import CliRunner

runner = CliRunner()


def invoke(root, *args):
    start = time.perf_counter()
    result = runner.invoke(app, ["--project", str(root), "--json", *args])
    assert result.exit_code == 0, result.output
    return json.loads(result.stdout)["data"], time.perf_counter() - start


@pytest.mark.slow
def test_two_corpus_profiles_and_reproducibility(tmp_path, monkeypatch):
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1700000000")
    roots = []
    clean_bytes = None
    for profile, run_name in (
        ("clean-scan", "clean-a"),
        ("phone-tilt", "tilt"),
        ("clean-scan", "clean-b"),
    ):
        root = tmp_path / run_name
        roots.append(root)
        # Exercise the actual console entry point at least once, as installed by uv.
        subprocess.run(
            ["glyphlab", "new", "E2EHand", "--family-name", "E2EHand", "--dir", str(root)],
            check=True,
            capture_output=True,
            text=True,
            env=os.environ.copy(),
        )
        template, _ = invoke(root, "template")
        sidecar = read_sidecar(Path(template["sidecar"]))
        manifests = generate_corpus(
            Path(template["pdf"]), sidecar, profile, None, 42, root / "scans"
        )
        expected = {
            int(cp[2:], 16) for path in manifests for cp in json.loads(path.read_text())["inked"]
        }
        ingest, elapsed = invoke(root, "ingest")
        assert ingest["coverage"]["have"] == len(expected)
        assert sum(p["counts"]["failed"] for p in ingest["pages"]) == 0
        assert elapsed / len(manifests) <= 22.5
        print(f"{profile}: ingest {elapsed / len(manifests):.3f} seconds/page", flush=True)
        invoke(root, "accept", "--all-auto")
        built, build_elapsed = invoke(root, "build")
        assert build_elapsed <= 15
        print(f"{profile}: build {build_elapsed:.3f} seconds", flush=True)
        assert built["qa"]["passed"]
        with TTFont(built["ttf"]) as font:
            assert set(font.getBestCmap()) == expected | {32, 0x3000}
            for cp, name in font.getBestCmap().items():
                if cp >= 0x3000:
                    assert font["hmtx"][name][0] == 1000
        original = Path(built["ttf"]).read_bytes()
        if profile == "clean-scan":
            if clean_bytes is None:
                clean_bytes = original
            else:
                assert original == clean_bytes, "Fresh full journeys must produce identical fonts"
        repeated, _ = invoke(root, "build")
        assert Path(repeated["ttf"]).read_bytes() == original
        assert "Content-Security-Policy" in Path(built["proof"]).read_text()
        assert "data:font/woff2;base64," in Path(built["proof"]).read_text()
    root = roots[0]
    # New tilted scan bytes exercise accepted protection, rather than the hash skip path.
    template, _ = invoke(root, "template")
    manifests = generate_corpus(
        Path(template["pdf"]),
        read_sidecar(Path(template["sidecar"])),
        "phone-tilt",
        None,
        42,
        root / "tilted",
    )
    previous = ProjectStore(root).read_status()
    rescanned, _ = invoke(
        root,
        "ingest",
        *[str(p.with_name(p.name.replace(".manifest.json", ".jpg"))) for p in manifests],
    )
    assert sum(page["counts"]["skipped_accepted"] for page in rescanned["pages"]) == len(previous)
    assert ProjectStore(root).read_status() == previous

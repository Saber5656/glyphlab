import json
from pathlib import Path
from uuid import UUID

import numpy as np
import pytest
from glyphlab.charset import get_preset
from glyphlab.ingest.decode import decode_scan, sniff_format
from glyphlab.template import generate_template
from glyphlab.template.layout import cell_box_px
from glyphlab.template.sidecar import read_sidecar
from PIL import Image

from .generate import generate_corpus


@pytest.fixture(scope="module")
def artifacts(tmp_path_factory):
    artifacts = generate_template(
        tmp_path_factory.mktemp("corpus-template"), get_preset("ja-basic-v1"), UUID(int=1), "Test"
    )
    return artifacts, read_sidecar(artifacts.sidecar_path)


@pytest.mark.parametrize("profile", ["clean-scan", "phone-tilt", "phone-dark", "crumpled"])
def test_deterministic_manifests_and_valid_images(artifacts, tmp_path, profile):
    template, sidecar = artifacts
    runs = []
    for run in ("a", "b"):
        directory = tmp_path / run
        manifests = generate_corpus(template.pdf_path, sidecar, profile, [0], 42, directory)
        manifest = json.loads(manifests[0].read_text())
        assert set(manifest) == {
            "schema",
            "profile",
            "seed",
            "template_id",
            "page_index",
            "inked",
            "empty_cells",
        }
        assert manifest["schema"] == "glyphlab.corpus-manifest/1"
        assert len(manifest["inked"]) == 48 and len(manifest["empty_cells"]) == 1
        assert set(manifest["inked"]).isdisjoint(manifest["empty_cells"])
        assert set(manifest["inked"] + manifest["empty_cells"]) == {
            f"U+{cell.codepoint:04X}" for cell in sidecar.pages[0].cells
        }
        path = directory / f"page-0.{'png' if profile == 'clean-scan' else 'jpg'}"
        data = path.read_bytes()
        assert len(data) <= 12 * 2**20 and sniff_format(data[:32]) in ("png", "jpeg")
        assert decode_scan(data).shape == (3508, 2481)
        runs.append((data, manifests[0].read_bytes()))
    assert runs[0] == runs[1]


def test_clean_golden_crops(artifacts, tmp_path):
    template, sidecar = artifacts
    generate_corpus(template.pdf_path, sidecar, "clean-scan", [0, 1], 42, tmp_path)
    for cp, label in [(65, "A"), (120, "x")]:
        page = next(p for p in sidecar.pages if any(c.codepoint == cp for c in p.cells))
        cell = next(c for c in page.cells if c.codepoint == cp)
        x0, y0, x1, y1 = cell_box_px(page, cell.row, cell.col)
        cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
        with Image.open(tmp_path / f"page-{page.index}.png") as image:
            actual = np.asarray(image.crop((cx - 64, cy - 64, cx + 64, cy + 64)), dtype=float)
        expected = np.asarray(
            Image.open(Path(__file__).parent / f"golden-clean-{label}.png"), dtype=float
        )
        assert np.abs(actual - expected).mean() <= 2

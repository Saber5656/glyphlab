"""Regenerate template and tiny corpus raster references from pinned inputs."""

import sys
import tempfile
from pathlib import Path
from uuid import UUID

import pypdfium2 as pdfium
from glyphlab.charset import get_preset
from glyphlab.template import generate_template
from glyphlab.template.layout import cell_box_px
from glyphlab.template.sidecar import read_sidecar
from PIL import Image

TESTS = Path(__file__).parents[1]
sys.path.insert(0, str(TESTS))
from corpus.generate import generate_corpus  # noqa: E402 -- test-only module path


def update_golden():
    with tempfile.TemporaryDirectory() as work:
        root = Path(work)
        artifacts = generate_template(
            root / "template", get_preset("ja-basic-v1"), UUID(int=1), "Test"
        )
        with pdfium.PdfDocument(artifacts.pdf_path) as pdf:
            (TESTS / "artifacts").mkdir(exist_ok=True)
            pdf[0].render(scale=150 / 72).to_pil().save(TESTS / "artifacts/template-page0.png")
        sidecar = read_sidecar(artifacts.sidecar_path)
        generate_corpus(artifacts.pdf_path, sidecar, "clean-scan", [0, 1], 42, root / "corpus")
        for cp, label in [(65, "A"), (120, "x")]:
            page = next(p for p in sidecar.pages if any(c.codepoint == cp for c in p.cells))
            cell = next(c for c in page.cells if c.codepoint == cp)
            x0, y0, x1, y1 = cell_box_px(page, cell.row, cell.col)
            cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
            with Image.open(root / "corpus" / f"page-{page.index}.png") as image:
                image.crop((cx - 64, cy - 64, cx + 64, cy + 64)).save(
                    TESTS / "corpus" / f"golden-clean-{label}.png"
                )


if __name__ == "__main__":
    update_golden()

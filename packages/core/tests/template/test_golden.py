from pathlib import Path
from uuid import UUID

import numpy as np
import pypdfium2 as pdfium
from glyphlab.charset import get_preset
from glyphlab.template import generate_template
from PIL import Image


def test_printed_template_golden(tmp_path):
    artifacts = generate_template(tmp_path, get_preset("ja-basic-v1"), UUID(int=1), "Test")
    with pdfium.PdfDocument(artifacts.pdf_path) as pdf:
        actual = np.asarray(pdf[0].render(scale=150 / 72).to_pil(), dtype=float)
    golden = np.asarray(
        Image.open(Path(__file__).parents[1] / "artifacts/template-page0.png"), dtype=float
    )
    assert np.abs(actual - golden).mean() <= 2

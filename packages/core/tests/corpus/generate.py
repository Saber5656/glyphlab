"""Deterministic, licensed synthetic handwriting; test support, never shipped."""

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

import cv2
import numpy as np
import pypdfium2 as pdfium
from glyphlab.template.layout import cell_box_px
from glyphlab.template.sidecar import TemplateSidecar, read_sidecar
from PIL import Image, ImageDraw, ImageFilter, ImageFont

FONT = Path(__file__).parent / "fonts" / "KleeOne-Regular.ttf"


@dataclass(frozen=True)
class Profile:
    tilt: bool = False
    brightness: float = 1.0
    noise: float = 0.0
    crumple: bool = False


PROFILES = {
    "clean-scan": Profile(),
    "phone-tilt": Profile(True),
    "phone-dark": Profile(True, 0.55, 6),
    "crumpled": Profile(True, 1, 0, True),
}


def generate_corpus(
    template_pdf: Path,
    sidecar: TemplateSidecar,
    profile: str,
    pages: list[int] | None,
    seed: int,
    out_dir: Path,
    fill_fraction: float = 1.0,
) -> list[Path]:
    if not 0 <= fill_fraction <= 1:
        raise ValueError("fill_fraction must be between zero and one")
    spec = PROFILES[profile]
    out_dir.mkdir(parents=True, exist_ok=True)
    manifests = []
    with pdfium.PdfDocument(template_pdf) as pdf:
        for page in sidecar.pages:
            if pages is not None and page.index not in pages:
                continue
            rng = np.random.default_rng(np.random.SeedSequence([seed, page.index]))
            image = pdf[page.index].render(scale=300 / 72).to_pil().convert("L")
            mapped = page.cells_with_chars()
            n_ink = max(
                0,
                int(len(mapped) * fill_fraction) - round(len(mapped) * fill_fraction * 0.03),
            )
            indices = {int(i) for i in rng.choice(len(mapped), n_ink, replace=False)}
            inked = []
            empty = []
            for index, cell in enumerate(mapped):
                cp = f"U+{cell.codepoint:04X}"
                if index not in indices:
                    empty.append(cp)
                    continue
                x0, y0, x1, y1 = cell_box_px(page, cell.row, cell.col)
                # Single-character stamps do not need shaping. Pillow's default
                # switches to RAQM when the host provides libraqm, shifting ink.
                font = ImageFont.truetype(str(FONT), 260, layout_engine=ImageFont.Layout.BASIC)
                box = font.getbbox(chr(cell.codepoint))
                glyph = Image.new("L", (box[2] - box[0] + 12, box[3] - box[1] + 12), 255)
                ImageDraw.Draw(glyph).text(
                    (6 - box[0], 6 - box[1]),
                    chr(cell.codepoint),
                    font=font,
                    fill=int(rng.integers(30, 61)),
                )
                # Every stamped mark has measurable ink above the documented 0.5% gate;
                # tiny punctuation is written deliberately boldly in the fixture.
                area = np.count_nonzero(np.asarray(glyph) < 128)
                scale = min((x1 - x0 - 32) / glyph.width, (y1 - y0 - 42) / glyph.height)
                if area * scale * scale < 550:
                    scale = min(
                        max(scale, (550 / max(area, 1)) ** 0.5),
                        (x1 - x0 - 20) / glyph.width,
                        (y1 - y0 - 20) / glyph.height,
                    )
                scale *= float(rng.uniform(0.95, 1.0))
                glyph = glyph.resize(
                    (
                        max(1, round(glyph.width * scale)),
                        max(1, round(glyph.height * scale)),
                    ),
                    Image.Resampling.LANCZOS,
                )
                glyph = glyph.rotate(
                    float(rng.uniform(-3, 3)),
                    Image.Resampling.BICUBIC,
                    expand=True,
                    fillcolor=255,
                )
                px = x0 + (x1 - x0 - glyph.width) // 2 + int(rng.integers(-5, 6))
                py = y0 + (y1 - y0 - glyph.height) // 2 + int(rng.integers(-5, 6))
                image.paste(
                    Image.fromarray(
                        np.minimum(
                            np.asarray(image.crop((px, py, px + glyph.width, py + glyph.height))),
                            np.asarray(glyph),
                        )
                    ),
                    (px, py),
                )
                inked.append(cp)
            arr = np.asarray(image.filter(ImageFilter.GaussianBlur(0.5)))
            h, w = arr.shape
            if spec.tilt:
                # A bounded quadrilateral embeds the complete paper in the photograph.
                src = np.float32([[0, 0], [w - 1, 0], [w - 1, h - 1], [0, h - 1]])
                dst = np.float32(
                    [
                        [0.045 * w, 0.025 * h],
                        [0.975 * w, 0.055 * h],
                        [0.955 * w, 0.98 * h],
                        [0.025 * w, 0.95 * h],
                    ]
                )
                transform = cv2.getPerspectiveTransform(src, dst)
                arr = cv2.warpPerspective(arr, transform, (w, h), borderValue=235)
                yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
                vignette = 1 - 0.10 * ((xx / w - 0.5) ** 2 + (yy / h - 0.5) ** 2)
                arr = np.clip(arr * vignette, 0, 255).astype(np.uint8)
            if spec.brightness != 1 or spec.noise:
                gradient = np.linspace(0.875, 1.125, w, dtype=np.float32)[None, :]
                arr = np.clip(
                    arr.astype(np.float32) * spec.brightness * gradient
                    + rng.normal(0, spec.noise, arr.shape),
                    0,
                    255,
                ).astype(np.uint8)
            if spec.crumple:
                yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
                arr = cv2.remap(
                    arr,
                    xx + 35 * np.sin(yy / 210),
                    yy + 45 * np.sin(xx / 160),
                    cv2.INTER_LINEAR,
                    borderValue=255,
                )
            ext = "jpg" if spec.tilt else "png"
            image_path = out_dir / f"page-{page.index}.{ext}"
            Image.fromarray(arr).save(
                image_path,
                **(
                    {"quality": 70, "optimize": False, "progressive": False}
                    if ext == "jpg"
                    else {"compress_level": 6}
                ),
            )
            assert image_path.stat().st_size <= 12 * 2**20 and w * h <= 36_000_000
            manifest = {
                "schema": "glyphlab.corpus-manifest/1",
                "profile": profile,
                "seed": seed,
                "template_id": sidecar.template_id,
                "page_index": page.index,
                "inked": sorted(inked),
                "empty_cells": sorted(empty),
            }
            manifest_path = out_dir / f"page-{page.index}.manifest.json"
            manifest_path.write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n")
            manifests.append(manifest_path)
    return manifests


if __name__ == "__main__":
    from glyphlab.charset import get_preset
    from glyphlab.template import generate_template

    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", choices=PROFILES, default="clean-scan")
    parser.add_argument("--page", type=int, default=0)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    artifacts = generate_template(
        args.out / "template",
        get_preset("ja-basic-v1"),
        UUID(int=1),
        "Synthetic corpus",
    )
    generate_corpus(
        artifacts.pdf_path,
        read_sidecar(artifacts.sidecar_path),
        args.profile,
        [args.page],
        args.seed,
        args.out,
    )

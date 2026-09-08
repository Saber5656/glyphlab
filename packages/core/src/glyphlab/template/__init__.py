from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

from glyphlab.charset import CharsetSpec

from .layout import compute_layout
from .pdf import render_pdf
from .sidecar import write_sidecar


@dataclass(frozen=True)
class TemplateArtifacts:
    pdf_path: Path
    sidecar_path: Path
    page_count: int


def generate_template(
    out_dir: Path, charset: CharsetSpec, template_id: UUID, project_name: str
) -> TemplateArtifacts:
    out_dir.mkdir(parents=True, exist_ok=True)
    layout = compute_layout(charset)
    pdf_path = out_dir / f"{charset.charset_id}.pdf"
    sidecar_path = out_dir / "template.json"
    render_pdf(pdf_path, layout, charset, str(template_id), project_name)
    write_sidecar(sidecar_path, layout, template_id, charset)
    return TemplateArtifacts(pdf_path, sidecar_path, layout.page_count)

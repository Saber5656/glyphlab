from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

from glyphlab.charset import CharsetSpec
from glyphlab.errors import GlyphlabError

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
    pdf_path, sidecar_path = template_paths(out_dir, charset)
    out_dir.mkdir(parents=True, exist_ok=True)
    layout = compute_layout(charset)
    render_pdf(pdf_path, layout, charset, str(template_id), project_name)
    write_sidecar(sidecar_path, layout, template_id, charset)
    return TemplateArtifacts(pdf_path, sidecar_path, layout.page_count)


def template_paths(out_dir: Path, charset: CharsetSpec) -> tuple[Path, Path]:
    """Validate template output paths for generation and restoration alike."""
    if any(c in charset.charset_id for c in ("/", "\\", "\x00")):
        raise GlyphlabError("E_VALIDATION", "Charset ID must be a safe filename component")
    root = out_dir.resolve()
    for filename in (f"{charset.charset_id}.pdf", "template.json"):
        if not (out_dir / filename).resolve().is_relative_to(root):
            raise GlyphlabError("E_VALIDATION", "Template output escapes its directory")
    return out_dir / f"{charset.charset_id}.pdf", out_dir / "template.json"

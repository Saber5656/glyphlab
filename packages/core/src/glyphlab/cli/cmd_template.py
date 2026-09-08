"""Generate templates while protecting previously printed sheets."""

import uuid

import typer

from glyphlab.cli.context import current, require_project, resolve_charset
from glyphlab.cli.render import cli_guard, success
from glyphlab.errors import GlyphlabError


@cli_guard
def template(
    regenerate: bool = False,
    yes: bool = False,
    open_pdf: bool = typer.Option(False, "--open"),
) -> None:
    from glyphlab.template import generate_template, template_paths
    from glyphlab.template.pdf import render_pdf
    from glyphlab.template.sidecar import read_sidecar

    ctx = current()
    config, store = require_project(ctx)
    charset = resolve_charset(config.project.charset, ctx.project_root)
    directory = store.root / "template"
    pdf, sidecar_path = template_paths(directory, charset)
    template_id = str(uuid.uuid4())
    pages = (sum(c.drawn for c in charset.chars) + 48) // 49
    if regenerate:
        typer.echo("Previously printed sheets must be thrown away and reprinted.", err=True)
        if not yes:
            import sys

            if not sys.stdin.isatty():
                raise GlyphlabError("E_VALIDATION", "pass --yes to confirm regeneration")
            if not typer.confirm(
                "Discard and reprint all previously printed sheets?", default=False
            ):
                raise typer.Exit(3)
    elif sidecar_path.exists():
        sidecar = read_sidecar(sidecar_path, expected_charset=charset)
        template_id = str(sidecar.template_id)
        pages = len(sidecar.pages)
        if not pdf.is_file():
            render_pdf(pdf, sidecar, charset, template_id, config.project.name)
        if pdf.is_file():
            success(
                {
                    "pdf": str(pdf),
                    "sidecar": str(sidecar_path),
                    "template_id": template_id,
                    "pages": pages,
                    "regenerated": False,
                },
                f"template up to date: {pdf}",
            )
            if open_pdf:
                typer.launch(str(pdf))
            return
    result = generate_template(directory, charset, uuid.UUID(template_id), config.project.name)
    success(
        {
            "pdf": str(result.pdf_path),
            "sidecar": str(result.sidecar_path),
            "template_id": template_id,
            "pages": result.page_count,
            "regenerated": regenerate,
        },
        f"{result.page_count} pages: {result.pdf_path}\n"
        "Print at 100% scale; check the 50 mm ruler.",
    )
    if open_pdf:
        typer.launch(str(result.pdf_path))


def register(app: typer.Typer) -> None:
    app.command()(template)

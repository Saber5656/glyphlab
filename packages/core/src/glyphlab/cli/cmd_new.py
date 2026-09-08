"""Create a validated local project without overwriting existing data."""

import re
from pathlib import Path
from typing import Annotated

import typer

from glyphlab.cli.context import resolve_charset
from glyphlab.cli.render import cli_guard, success
from glyphlab.errors import GlyphlabError
from glyphlab.project.config import ProjectConfig
from glyphlab.project.store import ProjectStore
from glyphlab.template.layout import compute_layout


@cli_guard
def new(
    name: str,
    charset: str = "ja-basic-v1",
    family_name: str | None = None,
    directory: Annotated[Path | None, typer.Option("--dir")] = None,
) -> None:
    family = family_name or name
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9 \-]{0,30}", family):
        raise GlyphlabError(
            "E_VALIDATION", "Pass --family-name with an ASCII font family (1–31 characters)"
        )
    slug = re.sub(r"[^a-z0-9-]", "", name.lower().replace(" ", "-"))
    if directory is None and not slug:
        raise GlyphlabError("E_VALIDATION", "Name has no ASCII directory slug; pass --dir")
    root = directory if directory is not None else Path(slug)
    spec = resolve_charset(charset, root)
    config = ProjectConfig.model_validate(
        {"project": {"name": name, "family_name": family, "charset": charset}}
    )
    pages = len(compute_layout(spec).pages)
    ProjectStore(root).init(config)
    success(
        {"root": str(root), "charset": spec.charset_id, "pages": pages},
        f"Created {root}\nNext: glyphlab --project {root} template → write → ingest → build",
    )


def register(app: typer.Typer) -> None:
    app.command()(new)

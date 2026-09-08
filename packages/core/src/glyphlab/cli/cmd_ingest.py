"""Incremental, sequential scan ingestion with per-page diagnostics."""

import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Literal

import typer

from glyphlab.cli.context import current, require_project, resolve_charset
from glyphlab.cli.render import cli_guard, success
from glyphlab.errors import GlyphlabError


@cli_guard
def ingest(
    files: Annotated[list[Path] | None, typer.Argument()] = None,
    force: bool = False,
    engine: Literal["auto", "potrace", "potracer"] | None = None,
    all_files: bool = typer.Option(False, "--all"),
) -> None:
    from glyphlab.ingest.orchestrator import ingest_scan
    from glyphlab.ingest.sinks import ProjectGlyphSink
    from glyphlab.template.sidecar import read_sidecar
    from glyphlab.vectorize import select_engine

    ctx = current()
    config, store = require_project(ctx)
    charset = resolve_charset(config.project.charset, ctx.project_root)
    path = store.root / "template/template.json"
    if not path.is_file():
        raise GlyphlabError("E_VALIDATION", "run `glyphlab template` first")
    sidecar = read_sidecar(path, expected_charset=charset)
    tracer = select_engine(engine or config.build.vectorizer)
    scans = files or store.list_scans()
    if not scans:
        raise GlyphlabError(
            "E_VALIDATION", "No input files; put JPEG, PNG, or HEIC scans in scans/"
        )
    index_path = store.root / "work/ingest-index.json"
    index_path.parent.mkdir(parents=True, exist_ok=True)
    index = json.loads(index_path.read_text()) if index_path.exists() else {}
    results = []
    failures = []
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%f")
    for number, scan in enumerate(scans):
        try:
            raw = scan.read_bytes()
            digest = hashlib.sha256(raw).hexdigest()
            if digest in index and not all_files and not force:
                continue
            report = ingest_scan(
                raw,
                sidecar=sidecar,
                charset=charset,
                store=ProjectGlyphSink(store),
                engine=tracer,
                force=force,
            )
            data = report.to_dict()
            report_path = store.root / f"work/ingest-{stamp}-{number}.json"
            report_path.write_text(json.dumps(data, indent=2) + "\n")
            results.append({"file": scan.name, **data})
            index[digest] = scan.name
            temp = index_path.with_suffix(".json.tmp")
            temp.write_text(json.dumps(index, sort_keys=True) + "\n")
            os.replace(temp, index_path)
        except (GlyphlabError, OSError) as exc:
            code = exc.code if isinstance(exc, GlyphlabError) else "E_VALIDATION"
            failures.append({"file": scan.name, "error_code": code, "message": str(exc)})
            typer.echo(f"{scan.name}: error[{code}]: {exc}", err=True)
    saved = store.read_status()
    coverage = sum(e["status"] != "missing" for e in saved.values())
    drawn = sum(c.drawn for c in charset.chars)
    data = {"pages": results, "errors": failures, "coverage": {"have": coverage, "total": drawn}}
    if failures:
        if not current().json_mode:
            typer.echo(
                "\n".join(f"{r['file']} | page {r['page_index']} | {r['counts']}" for r in results)
            )
            typer.echo(f"coverage: {coverage}/{drawn} drawn glyphs have sources")
        raise GlyphlabError("E_VALIDATION", "One or more input pages failed", detail=data)
    success(
        data,
        (
            "nothing new\n"
            if not results and not failures
            else "\n".join(f"{r['file']} | page {r['page_index']} | {r['counts']}" for r in results)
            + "\n"
        )
        + f"coverage: {coverage}/{drawn} drawn glyphs have sources",
    )


def register(app: typer.Typer) -> None:
    app.command()(ingest)

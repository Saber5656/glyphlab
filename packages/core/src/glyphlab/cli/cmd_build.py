"""Build selected SVGs, always run structural QA, and write the proof even on failure."""

from datetime import UTC, datetime
from pathlib import Path

import typer

from glyphlab.cli.context import current, require_project, resolve_charset
from glyphlab.cli.render import cli_guard, success
from glyphlab.errors import GlyphlabError
from glyphlab.fontbuild.builder import build_font
from glyphlab.fontbuild.selection import collect_buildable_glyphs
from glyphlab.model import GlyphStatus, GlyphWarning
from glyphlab.project.glyph_svg import read_glyph_svg
from glyphlab.project.store import StatusEntry
from glyphlab.qa import ExpectedBuild, run_qa
from glyphlab.report.proof import ProofMeta, generate_proof


@cli_guard
def build(
    include_unreviewed: bool | None = typer.Option(None, "--include-unreviewed/--accepted-only"),
    skip_bakery: bool = False,
    completer: str = "none",
    out: Path | None = None,
) -> None:
    if completer != "none":
        raise typer.BadParameter("Only --completer none is supported")
    ctx = current()
    config, store = require_project(ctx)
    charset = resolve_charset(config.project.charset, ctx.project_root)
    include = config.build.include_unreviewed if include_unreviewed is None else include_unreviewed
    paths = collect_buildable_glyphs(store, include)
    if not paths:
        raise GlyphlabError("E_VALIDATION", "nothing to build; run ingest/accept")
    glyphs = {}
    errors = {}
    for cp, path in sorted(paths.items()):
        try:
            glyphs[cp] = read_glyph_svg(path)
        except (GlyphlabError, OSError) as exc:
            errors[path.name] = str(exc)
    if errors:
        raise GlyphlabError(
            "E_GLYPH_SVG_INVALID",
            "Invalid glyph SVGs: " + ", ".join(errors),
            detail={"files": errors},
        )
    statuses = store.read_status()
    automatic = sum(statuses[f"U+{cp:04X}"]["status"] == "auto" for cp in paths)
    if automatic:
        typer.echo(
            f"{automatic} unreviewed glyphs included; run 'glyphlab status' / 'accept' to review",
            err=True,
        )
    if skip_bakery:
        typer.echo("WARNING: Font Bakery skipped; structural QA is still required.", err=True)
    result = build_font(config, glyphs, charset, out or store.build_dir())
    advances = {cp: advance for cp, (_, advance) in glyphs.items()}
    advances.update(
        {c.codepoint: 500 if c.codepoint == 32 else 1000 for c in charset.chars if not c.drawn}
    )
    qa = run_qa(
        result.ttf_path,
        charset,
        ExpectedBuild(set(advances), advances),
        require_bakery=not skip_bakery,
    )
    counts = dict.fromkeys(("missing", "auto", "accepted", "rejected"), 0)
    proof_statuses = {}
    for char in charset.chars:
        if not char.drawn:
            continue
        entry: StatusEntry = statuses.get(
            f"U+{char.codepoint:04X}", {"status": "missing", "warnings": [], "source": None}
        )
        state = GlyphStatus(entry["status"])
        counts[state.value] += 1
        # AUTO excluded by accepted-only must appear missing in this build's proof.
        proof_state = state if char.codepoint in glyphs else GlyphStatus.MISSING
        proof_statuses[char.codepoint] = (
            proof_state,
            [GlyphWarning(w) for w in entry.get("warnings", [])],
        )
    counts["built"] = len(advances)
    proof = generate_proof(
        result.ttf_path.parent / "proof.html",
        woff2_bytes=result.woff2_path.read_bytes(),
        project=config,
        charset=charset,
        statuses=proof_statuses,
        qa=qa,
        meta=ProofMeta(
            charset.charset_id,
            charset.version,
            config.project.version,
            datetime.now(UTC).isoformat(),
            counts,
        ),
    )
    fails = [finding.check_id for finding in qa.findings if finding.severity == "FAIL"]
    data: dict[str, object] = {
        "ttf": str(result.ttf_path),
        "woff2": str(result.woff2_path),
        "proof": str(proof),
        "qa": {"passed": qa.passed, "fails": fails},
        "glyphs": {"built": len(advances), "missing": result.missing},
    }
    if not qa.passed:
        raise GlyphlabError("E_QA_FAILED", "Font QA failed: " + ", ".join(fails), detail=data)
    success(data, f"TTF: {result.ttf_path}\nWOFF2: {result.woff2_path}\nProof: {proof}\nQA: PASS")


def register(app: typer.Typer) -> None:
    app.command()(build)

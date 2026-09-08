"""The local-only glyphlab command line interface."""

from pathlib import Path
from typing import Annotated

import typer

from glyphlab import __version__
from glyphlab.cli.context import CliContext, bind
from glyphlab.cli.group import JsonGroup
from glyphlab.cli.render import cli_guard, success
from glyphlab.errors import ERROR_REGISTRY, GlyphlabError

app = typer.Typer(no_args_is_help=True, add_completion=True, cls=JsonGroup)


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    project: Annotated[Path, typer.Option("--project", help="Local project directory")] = Path("."),
    json_mode: bool = typer.Option(False, "--json", help="Emit a machine-readable JSON envelope"),
    verbose: bool = typer.Option(False, "--verbose", help="Show detailed diagnostics"),
    version: bool = typer.Option(False, "--version", is_eager=True),
) -> None:
    ctx.obj = CliContext(project, json_mode, verbose)
    bind(ctx.obj)
    if version:
        typer.echo(__version__)
        raise typer.Exit()


@app.command("_selftest", hidden=True)
@cli_guard
def selftest(
    ok: bool = False,
    raise_code: str | None = typer.Option(None, "--raise"),
    raise_unexpected: bool = False,
    bad_param: bool = False,
) -> None:
    if bad_param:
        raise typer.BadParameter("selftest usage error")
    if raise_unexpected:
        raise RuntimeError("selftest unexpected error")
    if raise_code:
        if raise_code not in ERROR_REGISTRY:
            raise typer.BadParameter("Unknown error code")
        raise GlyphlabError(raise_code, "selftest expected error")
    success(None)


def register_commands() -> None:
    from glyphlab.cli import (
        cmd_build,
        cmd_charset,
        cmd_ingest,
        cmd_new,
        cmd_review,
        cmd_status,
        cmd_template,
    )

    for module in (
        cmd_build,
        cmd_charset,
        cmd_ingest,
        cmd_new,
        cmd_review,
        cmd_status,
        cmd_template,
    ):
        module.register(app)


register_commands()

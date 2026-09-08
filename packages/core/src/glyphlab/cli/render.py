"""Exactly one JSON envelope per command; diagnostics always go to stderr."""

from __future__ import annotations

import functools
import json
import traceback
from collections.abc import Callable
from typing import ParamSpec, TypeVar

import typer
from pydantic import ValidationError

from glyphlab.cli.context import current
from glyphlab.errors import ERROR_REGISTRY, GlyphlabError, to_glyphlab_error

P = ParamSpec("P")
R = TypeVar("R")


def success(data: object, human: str = "") -> None:
    if current().json_mode:
        typer.echo(json.dumps({"ok": True, "data": data}, ensure_ascii=False, default=str))
    elif human:
        typer.echo(human)


def failure(code: str, message: str, detail: dict[str, object] | None = None) -> None:
    typer.echo(f"error[{code}]: {message}", err=True)
    if current().verbose and detail:
        typer.echo(json.dumps(detail, indent=2, default=str), err=True)
    if current().json_mode:
        typer.echo(
            json.dumps(
                {"ok": False, "error": {"code": code, "message": message, "detail": detail}},
                default=str,
            )
        )


def cli_guard(func: Callable[P, R]) -> Callable[P, R]:
    @functools.wraps(func)
    def wrapped(*args: P.args, **kwargs: P.kwargs) -> R:
        try:
            return func(*args, **kwargs)
        except typer.Exit:
            raise
        except typer.BadParameter as exc:
            failure("E_USAGE", str(exc))
            raise typer.Exit(2) from exc
        except GlyphlabError as exc:
            failure(exc.code, str(exc), exc.detail)
            raise typer.Exit(ERROR_REGISTRY[exc.code].cli_exit) from exc
        except (ValidationError, ValueError, OSError) as exc:
            failure("E_VALIDATION", str(exc))
            raise typer.Exit(3) from exc
        except Exception as exc:
            mapped = to_glyphlab_error(exc)
            if mapped.code == "E_VALIDATION":
                failure(mapped.code, str(mapped), mapped.detail)
                raise typer.Exit(3) from exc
            failure("E_INTERNAL", f"{exc}; use --verbose for details")
            if current().verbose:
                traceback.print_exc()
            raise typer.Exit(1) from exc

    return wrapped

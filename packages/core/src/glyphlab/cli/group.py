"""Preserve JSON error envelopes even when parsing fails before a command starts."""

import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from typer._click.exceptions import ClickException
from typer.core import TyperGroup

from glyphlab.cli.context import CliContext, bind, current
from glyphlab.cli.render import failure


class JsonGroup(TyperGroup):
    def main(
        self,
        args: Sequence[str] | None = None,
        prog_name: str | None = None,
        complete_var: str | None = None,
        standalone_mode: bool = True,
        windows_expand_args: bool = True,
        **extra: Any,
    ) -> Any:
        values = list(sys.argv[1:] if args is None else args)
        options = values[: values.index("--")] if "--" in values else values
        json_mode = "--json" in options
        if not json_mode:
            return super().main(
                values, prog_name, complete_var, standalone_mode, windows_expand_args, **extra
            )
        bind(CliContext(Path("."), True, "--verbose" in options))
        try:
            result = super().main(
                values, prog_name, complete_var, False, windows_expand_args, **extra
            )
        except ClickException as exc:
            state = current()
            bind(CliContext(state.project_root, True, state.verbose))
            failure("E_USAGE", exc.format_message())
            result = exc.exit_code
        if standalone_mode:
            raise SystemExit(result if isinstance(result, int) else 0)
        return result

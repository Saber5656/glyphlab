"""Inspect the immutable preset or custom charset contract."""

from collections import Counter
from pathlib import Path

import typer

from glyphlab.cli.context import resolve_charset
from glyphlab.cli.render import cli_guard, success
from glyphlab.template.layout import compute_layout


@cli_guard
def list_charsets() -> None:
    rows = []
    for identifier in ("ascii", "kana", "ja-basic-v1"):
        spec = resolve_charset(identifier, Path.cwd())
        drawn = sum(char.drawn for char in spec.chars)
        rows.append(
            {
                "id": identifier,
                "version": spec.version,
                "encoded": len(spec.chars),
                "drawn": drawn,
                "pages": len(compute_layout(spec).pages),
            }
        )
    success(
        rows,
        "id | version | encoded | drawn | pages\n"
        + "\n".join(" | ".join(str(v) for v in row.values()) for row in rows),
    )


@cli_guard
def show_charset(identifier: str, codepoints: bool = False) -> None:
    spec = resolve_charset(identifier, Path.cwd())
    chars = [
        {
            "codepoint": f"U+{c.codepoint:04X}",
            "char": chr(c.codepoint),
            "script_class": c.script_class,
            "drawn": c.drawn,
        }
        for c in spec.chars
    ]
    drawn = sum(c.drawn for c in spec.chars)
    data: dict[str, object] = {
        "id": spec.charset_id,
        "version": spec.version,
        "encoded": len(chars),
        "drawn": drawn,
        "pages": len(compute_layout(spec).pages),
    }
    scripts = dict(Counter(c.script_class for c in spec.chars))
    data["scripts"] = scripts
    if codepoints:
        data["chars"] = chars
    human = (
        f"{spec.charset_id}@{spec.version}: {len(chars)} encoded, "
        f"{drawn} drawn, {len(compute_layout(spec).pages)} pages"
    )
    human += "\n" + ", ".join(f"{kind}: {count}" for kind, count in scripts.items())
    if codepoints:
        human += "\n" + "\n".join(
            f"{c['codepoint']} {c['char']} {c['script_class']} "
            f"{'drawn' if c['drawn'] else 'synthesized'}"
            for c in chars
        )
    success(data, human)


def register(app: typer.Typer) -> None:
    sub = typer.Typer(no_args_is_help=True)
    sub.command("list")(list_charsets)
    sub.command("show")(show_charset)
    app.add_typer(sub, name="charset")

"""CLI-local state and project resolution."""

from contextvars import ContextVar
from dataclasses import dataclass
from pathlib import Path

from glyphlab.charset.model import CharsetSpec
from glyphlab.charset.presets import get_preset
from glyphlab.errors import GlyphlabError
from glyphlab.project.charset_file import load_custom_charset
from glyphlab.project.config import ProjectConfig, load_config
from glyphlab.project.store import ProjectStore


@dataclass
class CliContext:
    project_root: Path
    json_mode: bool = False
    verbose: bool = False


_context: ContextVar[CliContext] = ContextVar("glyphlab_cli_context")


def bind(context: CliContext) -> None:
    _context.set(context)


def current() -> CliContext:
    return _context.get()


def require_project(ctx: CliContext) -> tuple[ProjectConfig, ProjectStore]:
    path = ctx.project_root / "glyphlab.toml"
    if not path.is_file():
        raise GlyphlabError("E_VALIDATION", "not a glyphlab project; run `glyphlab new`")
    return load_config(path), ProjectStore(ctx.project_root)


def resolve_charset(value: str, root: Path) -> CharsetSpec:
    if value.endswith(".toml"):
        return load_custom_charset(root / value)
    return get_preset(value)

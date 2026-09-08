"""Pydantic project configuration and charset loading."""

import re
import tomllib
import unicodedata
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from glyphlab.charset import CharsetSpec, get_preset
from glyphlab.errors import ConfigError
from glyphlab.project.charset_file import load_custom_charset


def validate_project_name(value: str) -> str:
    normalized = unicodedata.normalize("NFC", value)
    if not 1 <= len(normalized) <= 64:
        raise ValueError("project.name must contain 1-64 characters")
    if normalized != normalized.strip():
        raise ValueError("project.name must not have leading or trailing whitespace")
    if any((ord(char) < 0x20 or 0x7F <= ord(char) <= 0x9F) for char in normalized):
        raise ValueError("project.name must not contain control characters")
    return normalized


def validate_family_name(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9 \-]{0,30}", value):
        raise ValueError("project.family_name must match the TTF family name pattern")
    return value


class ProjectSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    family_name: str
    charset: str
    version: int = Field(default=1, ge=1)

    _name = field_validator("name")(validate_project_name)
    _family_name = field_validator("family_name")(validate_family_name)

    @field_validator("charset")
    @classmethod
    def validate_charset(cls, value: str) -> str:
        if value.endswith(".toml"):
            path = Path(value)
            if not path.is_absolute() and ".." in path.parts:
                raise ValueError("project.charset must be a relative .toml path")
            return value
        get_preset(value)
        return value


class BuildConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    include_unreviewed: bool = True
    vectorizer: Literal["auto", "potrace", "potracer"] = "auto"


class CustomCharsetConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    version: int = Field(ge=1)
    chars: list[str]


class ProjectConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_: Literal["glyphlab.project/1"] = Field(default="glyphlab.project/1", alias="schema")
    project: ProjectSettings
    build: BuildConfig = BuildConfig()
    custom_charset: CustomCharsetConfig | None = None


def _validation_error(exc: ValidationError) -> ConfigError:
    detail: dict[str, object] = {
        "fields": [".".join(str(part) for part in item["loc"]) for item in exc.errors()]
    }
    return ConfigError("invalid glyphlab.toml", detail=detail)


def load_config(path: Path) -> ProjectConfig:
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
        return ProjectConfig.model_validate(data)
    except ValidationError as exc:
        raise _validation_error(exc) from exc
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise ConfigError(f"could not read configuration: {exc}") from exc


def write_config(path: Path, config: ProjectConfig) -> None:
    lines = [
        'schema = "glyphlab.project/1"',
        "",
        "[project]",
        f"name = {_toml_string(config.project.name)}",
        f"family_name = {_toml_string(config.project.family_name)}",
        f"charset = {_toml_string(config.project.charset)}",
        f"version = {config.project.version}",
        "",
        "[build]",
        f"include_unreviewed = {str(config.build.include_unreviewed).lower()}",
        f"vectorizer = {_toml_string(config.build.vectorizer)}",
    ]
    if config.custom_charset is not None:
        lines.extend(
            [
                "",
                "[custom_charset]",
                f"name = {_toml_string(config.custom_charset.name)}",
                f"version = {config.custom_charset.version}",
                "chars = ["
                + ", ".join(_toml_string(item) for item in config.custom_charset.chars)
                + "]",
            ]
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _toml_string(value: str) -> str:
    import json

    return json.dumps(value, ensure_ascii=False)


def load_charset(charset: str, root: Path) -> CharsetSpec:
    """Resolve a preset or a project-relative custom charset file."""
    if not charset.endswith(".toml"):
        return get_preset(charset)
    path = Path(charset)
    if not path.is_absolute() and ".." in path.parts:
        raise ConfigError(
            "custom charset path must remain inside the project", detail={"path": charset}
        )
    return load_custom_charset(path if path.is_absolute() else root / path)


get_charset = load_charset

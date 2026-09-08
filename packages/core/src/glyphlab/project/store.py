"""Local project directory and atomic status persistence."""

import json
import os
from pathlib import Path
from typing import TypedDict

from glyphlab.errors import ConfigError
from glyphlab.model import Glyph
from glyphlab.project.config import ProjectConfig, write_config
from glyphlab.project.glyph_svg import render_glyph_svg


class StatusSource(TypedDict):
    upload: str
    cell: int


class StatusEntry(TypedDict):
    status: str
    warnings: list[str]
    source: StatusSource | None


StatusData = dict[str, StatusEntry]


class ProjectStore:
    def __init__(self, root: Path) -> None:
        self.root = root

    def init(self, config: ProjectConfig) -> None:
        if self.root.exists() and any(self.root.iterdir()):
            raise ConfigError("project directory must be empty")
        self.root.mkdir(parents=True, exist_ok=True)
        for directory in ("template", "scans", "work", "glyphs", "build"):
            (self.root / directory).mkdir(exist_ok=True)
        write_config(self.root / "glyphlab.toml", config)
        self.write_status({})

    def glyph_svg_path(self, codepoint: int) -> Path:
        if codepoint < 0 or codepoint > 0x10FFFF or 0xD800 <= codepoint <= 0xDFFF:
            raise ValueError("invalid Unicode codepoint")
        return self.root / "glyphs" / f"U+{codepoint:04X}.svg"

    def read_status(self) -> StatusData:
        path = self.root / "glyphs" / "status.json"
        try:
            data: object = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ConfigError(f"invalid status.json: {exc}") from exc
        if not isinstance(data, dict):
            raise ConfigError("status.json must contain an object")
        validated: StatusData = {}
        for key, raw_entry in data.items():
            if not isinstance(key, str) or not isinstance(raw_entry, dict):
                raise ConfigError("status.json entries must be objects keyed by strings")
            status = raw_entry.get("status")
            warnings = raw_entry.get("warnings")
            source = raw_entry.get("source")
            if (
                not isinstance(status, str)
                or not isinstance(warnings, list)
                or not all(isinstance(warning, str) for warning in warnings)
            ):
                raise ConfigError(f"invalid status entry: {key}")
            if source is not None:
                if (
                    not isinstance(source, dict)
                    or not isinstance(source.get("upload"), str)
                    or not isinstance(source.get("cell"), int)
                    or isinstance(source.get("cell"), bool)
                ):
                    raise ConfigError(f"invalid status source: {key}")
                typed_source: StatusSource | None = {
                    "upload": source["upload"],
                    "cell": source["cell"],
                }
            else:
                typed_source = None
            validated[key] = {"status": status, "warnings": warnings, "source": typed_source}
        return validated

    def write_status(self, status: StatusData) -> None:
        path = self.root / "glyphs" / "status.json"
        temp = path.with_name("status.json.tmp")
        payload = json.dumps(status, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        temp.write_text(payload, encoding="utf-8")
        try:
            os.replace(temp, path)
        except BaseException:
            try:
                temp.unlink()
            except OSError:
                pass
            raise

    def get_status(self, codepoint: int) -> StatusEntry | None:
        return self.read_status().get(f"U+{codepoint:04X}")

    def put_glyph(self, glyph: Glyph, svg_bytes: bytes | None = None) -> None:
        payload = render_glyph_svg(glyph) if svg_bytes is None else svg_bytes
        path = self.glyph_svg_path(glyph.codepoint)
        temp = path.with_suffix(".svg.tmp")
        temp.write_bytes(payload)
        os.replace(temp, path)
        status = self.read_status()
        status[f"U+{glyph.codepoint:04X}"] = {
            "status": glyph.status.value,
            "warnings": [warning.value for warning in glyph.warnings],
            "source": (
                {"upload": glyph.source.upload, "cell": glyph.source.cell}
                if glyph.source is not None
                else None
            ),
        }
        self.write_status(status)

    def list_scans(self) -> list[Path]:
        scan_dir = self.root / "scans"
        if not scan_dir.exists():
            return []
        allowed = {".jpg", ".jpeg", ".png", ".heic"}
        return sorted(
            (
                path
                for path in scan_dir.iterdir()
                if path.is_file() and path.suffix.lower() in allowed
            ),
            key=lambda path: path.name,
        )

    def ingest_report_path(self, timestamp: str) -> Path:
        return self.root / "work" / f"ingest-{timestamp}.json"

    def build_dir(self) -> Path:
        return self.root / "build"

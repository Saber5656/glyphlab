#!/usr/bin/env bash
set -euo pipefail
uv build --package glyphlab
uv run python scripts/readme_quickstart.py

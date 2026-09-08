#!/usr/bin/env bash
set -euo pipefail
uv run python - <<'PY'
import os
from packaging.version import Version
from glyphlab import __version__
tag=os.environ.get('TAG','')
if not tag.startswith('v') or Version(tag[1:]) != Version(__version__):
    raise SystemExit('Tag must be v<package version> and match glyphlab.__version__')
print('Tag and package version match')
PY

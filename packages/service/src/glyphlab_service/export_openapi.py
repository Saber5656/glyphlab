"""Deterministic contract export; this does not migrate or start background work."""

import argparse
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from glyphlab.errors import ERROR_REGISTRY

from .settings import Settings


def export_spec():
    from .app import create_app

    with TemporaryDirectory(prefix="glyphlab-openapi-") as tmp:
        app = create_app(Settings(data_dir=Path(tmp), environment="prod"), start_background=False)
        try:
            return app.openapi()
        finally:
            app.state.engine.dispose()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--error-codes", action="store_true")
    args = parser.parse_args()
    value = sorted(ERROR_REGISTRY) if args.error_codes else export_spec()
    print(json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

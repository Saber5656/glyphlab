"""Operational and privacy promises track executable configuration defaults."""

import re
from pathlib import Path

from glyphlab_service.settings import Settings

ROOT = Path(__file__).resolve().parents[3]


def test_settings_defaults_are_documented():
    guide = (ROOT / "docs/guide/self-host.md").read_text()
    for name, field in Settings.model_fields.items():
        default = field.default
        rendered = (
            '""'
            if default == ""
            else str(default).lower()
            if isinstance(default, bool)
            else str(default)
        )
        assert f"| `GLYPHLAB_{name.upper()}` | `{rendered}` |" in guide


def test_privacy_defaults_and_security_links():
    default_days = Settings.model_fields["retention_days"].default
    strings = (ROOT / "webui/src/i18n/ja.ts").read_text()
    assert re.search(rf"{int(default_days)}日", strings)
    assert Settings.model_fields["max_upload_bytes"].default == 12 * 2**20
    assert "security/advisories/new" in (ROOT / "SECURITY.md").read_text()
    assert 'path="/privacy"' in (ROOT / "webui/src/App.tsx").read_text()
    assert 'to="/privacy"' in (ROOT / "webui/src/pages/Landing.tsx").read_text()

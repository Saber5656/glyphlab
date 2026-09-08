from pathlib import Path

import pytest
from glyphlab.errors import ConfigError
from glyphlab.project.charset_file import load_custom_charset


def test_custom_charset_limits(tmp_path: Path) -> None:
    path = tmp_path / "custom.toml"
    path.write_text('name = "x"\nversion = 1\nchars = ["U+0041"]\n')
    assert load_custom_charset(path).get(0x41) is not None
    path.write_text('name = "x"\nversion = 1\nchars = ["U+D800"]\n')
    with pytest.raises(ConfigError):
        load_custom_charset(path)


def test_custom_charset_size_and_drawn_cap(tmp_path: Path) -> None:
    path = tmp_path / "custom.toml"
    path.write_bytes(b"x" * 4097)
    with pytest.raises(ConfigError):
        load_custom_charset(path)
    path.write_text(
        'name = "x"\nversion = 1\nchars = ['
        + ",".join(f'"U+{cp:04X}"' for cp in range(0x21, 0x21 + 501))
        + "]\n"
    )
    with pytest.raises(ConfigError):
        load_custom_charset(path)

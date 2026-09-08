from pathlib import Path

import pytest
from glyphlab.charset import CharsetSpec
from glyphlab.errors import ConfigError
from glyphlab.project.config import (
    BuildConfig,
    ProjectConfig,
    ProjectSettings,
    load_charset,
    load_config,
    validate_family_name,
    validate_project_name,
    write_config,
)


def make_config(charset: str = "ascii") -> ProjectConfig:
    return ProjectConfig(
        project=ProjectSettings(
            name="My handwriting", family_name="MyHand", charset=charset, version=1
        ),
        build=BuildConfig(),
    )


def test_config_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "glyphlab.toml"
    config = make_config()
    write_config(path, config)
    assert load_config(path) == config
    assert 'schema = "glyphlab.project/1"' in path.read_text()


@pytest.mark.parametrize("name", ["", " x", "x ", "x\x00y", "x" * 65])
def test_project_name_validation(name: str) -> None:
    with pytest.raises((ValueError, ConfigError)):
        validate_project_name(name)


def test_project_name_nfc() -> None:
    assert validate_project_name("Cafe\u0301") == "Café"


@pytest.mark.parametrize("family", ["日本語", "-bad", "a" * 32])
def test_family_validation(family: str) -> None:
    with pytest.raises((ValueError, ConfigError)):
        validate_family_name(family)


def test_bad_config_has_field_detail(tmp_path: Path) -> None:
    path = tmp_path / "bad.toml"
    path.write_text('[project]\nname = " x"\nfamily_name = "A"\ncharset = "ascii"\nversion = 1\n')
    with pytest.raises(ConfigError) as raised:
        load_config(path)
    assert raised.value.code == "E_VALIDATION"
    assert raised.value.detail


def test_load_charset_preset_and_custom(tmp_path: Path) -> None:
    assert isinstance(load_charset("ascii", tmp_path), CharsetSpec)
    custom = tmp_path / "custom.toml"
    custom.write_text('name = "my"\nversion = 2\nchars = ["U+3042-U+3044", "U+0020"]\n')
    loaded = load_charset("custom.toml", tmp_path)
    assert [char.codepoint for char in loaded.chars] == [0x20, 0x3042, 0x3043, 0x3044]
    assert loaded.get(0x3042) is not None and loaded.get(0x3042).script_class == "kana"
    assert loaded.get(0x20) is not None and not loaded.get(0x20).drawn

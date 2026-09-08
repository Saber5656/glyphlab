import os

import pytest
from hypothesis import settings


def pytest_configure() -> None:
    settings.register_profile("ci", max_examples=1000)
    settings.load_profile(os.environ.get("HYPOTHESIS_PROFILE", "default"))


@pytest.fixture
def golden_inputs():
    from support.font_fixtures import make_golden_inputs

    return make_golden_inputs()


@pytest.fixture
def golden_font(tmp_path, golden_inputs):
    from support.font_fixtures import make_golden_font

    return make_golden_font(tmp_path, golden_inputs)

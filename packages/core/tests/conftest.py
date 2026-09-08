from hypothesis import settings


def pytest_configure() -> None:
    settings.register_profile("ci", max_examples=1000)

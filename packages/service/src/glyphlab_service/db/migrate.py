from pathlib import Path

from alembic import command
from alembic.config import Config

from ..settings import Settings


def config(settings):
    cfg = Config()
    cfg.set_main_option("script_location", str(Path(__file__).parent / "migrations"))
    cfg.attributes["settings"] = settings
    return cfg


def upgrade(settings):
    command.upgrade(config(settings), "head")


def main():
    upgrade(Settings())

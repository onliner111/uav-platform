from __future__ import annotations

from alembic import command
from alembic.config import Config


def run_upgrade_head() -> None:
    config = Config("alembic.ini")
    command.upgrade(config, "head")


if __name__ == "__main__":
    run_upgrade_head()


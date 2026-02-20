from __future__ import annotations

import os
from collections.abc import Generator

from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlmodel import Session, create_engine

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://uav:uav@db:5432/uav_platform",
)

engine = create_engine(DATABASE_URL, pool_pre_ping=True)


def get_engine() -> Engine:
    return engine


def get_session() -> Generator[Session, None, None]:
    with Session(get_engine()) as session:
        yield session


def check_db_ready() -> bool:
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False

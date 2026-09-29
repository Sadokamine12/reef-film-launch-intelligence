from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session

from reef.config import settings


class Base(DeclarativeBase):
    pass


@lru_cache
def engine():
    cfg = settings()
    return create_engine(
        cfg.database_url,
        pool_pre_ping=True,
        pool_size=cfg.db_pool_size,
        max_overflow=0,
        connect_args={"prepare_threshold": None},
    )


def session():
    with Session(engine()) as db:
        try:
            yield db
        except Exception:
            db.rollback()
            raise

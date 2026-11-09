import os
from collections.abc import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import make_url
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./calendar_tasks.db")
def create_database_engine(url):
    """Configure SQLite contention handling without opening the DB on import."""
    address = make_url(url)
    if address.get_backend_name() != "sqlite":
        return create_engine(url)
    result = create_engine(url, connect_args={"check_same_thread": False, "timeout": 5})

    @event.listens_for(result, "connect")
    def configure_sqlite(connection, _):
        cursor = connection.cursor()
        try:
            cursor.execute("PRAGMA busy_timeout=5000")
            if address.database not in (None, "", ":memory:"):
                if cursor.execute("PRAGMA journal_mode").fetchone()[0].lower() != "wal":
                    cursor.execute("PRAGMA journal_mode=WAL")
        finally:
            cursor.close()

    return result


engine = create_database_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

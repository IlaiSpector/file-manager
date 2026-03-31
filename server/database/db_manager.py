"""Database manager for the server-side SQLite database.

This helper owns the SQLAlchemy engine and session lifecycle so authentication and other services
can access the database.
"""

from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from server.config import DATABASE_PATH
from server.database.models import Base


class DatabaseManager:
    """Create the SQLAlchemy engine and provide session helpers."""

    def __init__(
        self,
        database_path: Path | None = None,
    ) -> None:
        self.database_path = database_path or DATABASE_PATH
        self.database_url = self._build_sqlite_url(self.database_path)
        self.engine: Engine = create_engine(
            self.database_url,
            connect_args={"check_same_thread": False},
        )
        self._session_factory = sessionmaker(
            bind=self.engine,
            expire_on_commit=False,
        )

    @staticmethod
    def _build_sqlite_url(database_path: Path) -> str:
        """Convert a filesystem path into a SQLAlchemy SQLite URL."""
        return f"sqlite:///{database_path.as_posix()}"

    def initialize_database(self) -> None:
        """Create the SQLite file parent directory and all missing tables."""
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        Base.metadata.create_all(self.engine)

    @contextmanager
    def session_scope(self) -> Iterator[Session]:
        """Yield one session and handle commit/rollback automatically.

        This keeps transaction boundaries explicit: successful operations are
        committed, and any exception triggers a rollback before the error is
        re-raised to the caller.
        """
        session = self._session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

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
        """Convert a filesystem path into a SQLAlchemy SQLite URL.

        :param database_path: Filesystem path for the SQLite database file.
        :returns: SQLAlchemy connection URL for that SQLite file.
        """
        return f"sqlite:///{database_path.as_posix()}"

    def initialize_database(self) -> None:
        """Create the database directory and any missing schema objects.

        The method is safe to call more than once; existing tables are left in
        place by SQLAlchemy.
        """
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        Base.metadata.create_all(self.engine)

    @contextmanager
    def session_scope(self) -> Iterator[Session]:
        """Provide one transactional SQLAlchemy session.

        The yielded session is committed when the caller exits normally. Any
        exception triggers a rollback before the original error is re-raised.

        :returns: Context manager yielding one active SQLAlchemy session.
        :raises Exception: Re-raises any exception raised inside the managed
            block after rolling the transaction back.
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

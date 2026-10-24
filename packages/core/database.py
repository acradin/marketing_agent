from pathlib import Path
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker
from .models import Base


def database(url: str):
    if url.startswith("sqlite:///") and url != "sqlite:///:memory:":
        Path(url.removeprefix("sqlite:///")).parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(url, connect_args={"check_same_thread": False} if url.startswith("sqlite") else {})
    if url.startswith("sqlite"):
        @event.listens_for(engine, "connect")
        def pragmas(connection, _):
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("PRAGMA busy_timeout=10000")
    return engine, sessionmaker(engine, expire_on_commit=False)


def lock_write(session):
    if session.bind.dialect.name == "sqlite":
        session.execute(text("BEGIN IMMEDIATE"))

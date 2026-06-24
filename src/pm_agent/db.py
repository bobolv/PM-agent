from collections.abc import Generator
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.engine.url import make_url
from sqlmodel import Session, SQLModel, create_engine

from pm_agent.config import get_settings


def build_engine(database_url: str | None = None) -> Engine:
    url = database_url or get_settings().database_url
    _ensure_sqlite_parent_dir(url)
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    return create_engine(url, connect_args=connect_args)


def _ensure_sqlite_parent_dir(database_url: str) -> None:
    parsed_url = make_url(database_url)
    if not parsed_url.drivername.startswith("sqlite"):
        return

    database = parsed_url.database
    if not database or database == ":memory:":
        return

    Path(database).expanduser().parent.mkdir(parents=True, exist_ok=True)


engine = build_engine()


def init_db() -> None:
    SQLModel.metadata.create_all(engine)
    _ensure_sqlite_runtime_columns(engine)


def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session


def _ensure_sqlite_runtime_columns(db_engine: Engine) -> None:
    if not str(db_engine.url).startswith("sqlite"):
        return

    table_columns = {
        "projectdocument": {
            "plan_id": "INTEGER",
        },
        "documentgenerationrun": {
            "plan_id": "INTEGER",
            "source_work_record_ids": "JSON",
        },
        "documentcatalogitem": {
            "template_file_path": "VARCHAR",
            "updated_at": "DATETIME",
        },
    }
    with db_engine.begin() as connection:
        for table_name, columns in table_columns.items():
            existing = {
                row[1]
                for row in connection.execute(text(f"PRAGMA table_info({table_name})")).fetchall()
            }
            if not existing:
                continue
            for column_name, column_type in columns.items():
                if column_name not in existing:
                    connection.execute(
                        text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}")
                    )

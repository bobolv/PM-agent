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
        "projectdocumentplan": {
            "dependency_plan_ids": "JSON",
            "reference_document_ids": "JSON",
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
        connection.execute(
            text(
                "UPDATE projectdocumentplan "
                "SET dependency_plan_ids = '[]' "
                "WHERE dependency_plan_ids IS NULL"
            )
        )
        connection.execute(
            text(
                "UPDATE projectdocumentplan "
                "SET reference_document_ids = '[]' "
                "WHERE reference_document_ids IS NULL"
            )
        )
        _ensure_document_generation_run_template_nullable(connection)


def _ensure_document_generation_run_template_nullable(connection: object) -> None:
    columns = connection.execute(text("PRAGMA table_info(documentgenerationrun)")).fetchall()
    if not columns:
        return

    template_column = next((row for row in columns if row[1] == "template_id"), None)
    if template_column is None or not template_column[3]:
        return

    connection.execute(text("ALTER TABLE documentgenerationrun RENAME TO documentgenerationrun_old"))
    connection.execute(
        text(
            """
            CREATE TABLE documentgenerationrun (
                id INTEGER NOT NULL,
                project_id INTEGER NOT NULL,
                template_id INTEGER,
                plan_id INTEGER,
                document_id INTEGER,
                role_id INTEGER,
                prompt VARCHAR NOT NULL,
                context_md VARCHAR NOT NULL,
                source_document_ids JSON,
                source_artifact_ids JSON,
                source_work_record_ids JSON,
                created_at DATETIME NOT NULL,
                PRIMARY KEY (id),
                FOREIGN KEY(project_id) REFERENCES project (id),
                FOREIGN KEY(template_id) REFERENCES documenttemplate (id),
                FOREIGN KEY(plan_id) REFERENCES projectdocumentplan (id),
                FOREIGN KEY(document_id) REFERENCES projectdocument (id),
                FOREIGN KEY(role_id) REFERENCES projectrole (id)
            )
            """
        )
    )
    old_columns = {row[1] for row in columns}
    selectable_columns = [
        "id",
        "project_id",
        "template_id",
        "plan_id" if "plan_id" in old_columns else "NULL AS plan_id",
        "document_id",
        "role_id",
        "prompt",
        "context_md",
        "source_document_ids",
        "source_artifact_ids",
        "source_work_record_ids" if "source_work_record_ids" in old_columns else "'[]' AS source_work_record_ids",
        "created_at",
    ]
    connection.execute(
        text(
            "INSERT INTO documentgenerationrun "
            "(id, project_id, template_id, plan_id, document_id, role_id, prompt, context_md, "
            "source_document_ids, source_artifact_ids, source_work_record_ids, created_at) "
            f"SELECT {', '.join(selectable_columns)} FROM documentgenerationrun_old"
        )
    )
    connection.execute(text("DROP TABLE documentgenerationrun_old"))
    for column_name in ["project_id", "template_id", "plan_id", "document_id", "role_id"]:
        connection.execute(
            text(
                f"CREATE INDEX ix_documentgenerationrun_{column_name} "
                f"ON documentgenerationrun ({column_name})"
            )
        )

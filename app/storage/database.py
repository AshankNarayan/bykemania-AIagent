import os
import sqlite3
from pathlib import Path
from typing import Any, Optional

from dotenv import load_dotenv


load_dotenv()


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SQLITE_PATH = PROJECT_ROOT / "app" / "storage" / "agent_logs.sqlite3"


def get_database_type() -> str:
    """
    Returns selected database type.

    Local:
    DATABASE_TYPE=sqlite

    Future cloud:
    DATABASE_TYPE=postgres
    """

    return os.getenv("DATABASE_TYPE", "sqlite").strip().lower()


def get_database_url() -> str:
    """
    Returns DATABASE_URL from .env.
    """

    return os.getenv(
        "DATABASE_URL",
        "sqlite:///app/storage/agent_logs.sqlite3"
    ).strip()


def is_postgres() -> bool:
    return get_database_type() in ["postgres", "postgresql"]


def is_sqlite() -> bool:
    return get_database_type() == "sqlite"


def _resolve_sqlite_path(database_url: Optional[str] = None) -> Path:
    """
    Converts SQLite DATABASE_URL into a real file path.

    Supports:
    - sqlite:///app/storage/agent_logs.sqlite3
    - app/storage/agent_logs.sqlite3
    - C:/some/path/file.sqlite3
    """

    url = database_url or get_database_url()

    if url.startswith("sqlite:///"):
        raw_path = url.replace("sqlite:///", "", 1)
    else:
        raw_path = url

    sqlite_path = Path(raw_path)

    if not sqlite_path.is_absolute():
        sqlite_path = PROJECT_ROOT / sqlite_path

    sqlite_path.parent.mkdir(parents=True, exist_ok=True)

    return sqlite_path


def get_connection():
    """
    Returns database connection.
    """

    if is_postgres():
        return _get_postgres_connection()

    return _get_sqlite_connection()


def _get_sqlite_connection():
    sqlite_path = _resolve_sqlite_path()

    conn = sqlite3.connect(sqlite_path)
    conn.row_factory = sqlite3.Row

    return conn


def _get_postgres_connection():
    """
    PostgreSQL connection.

    Repository queries are being prepared for PostgreSQL compatibility.
    """

    try:
        import psycopg
        from psycopg.rows import dict_row
    except ImportError as exc:
        raise RuntimeError(
            "PostgreSQL support requires psycopg. "
            "Install it using: python -m pip install 'psycopg[binary]'"
        ) from exc

    database_url = get_database_url()

    if not database_url:
        raise RuntimeError("DATABASE_URL is required for PostgreSQL.")

    return psycopg.connect(
        database_url,
        row_factory=dict_row
    )


def normalize_query_for_database(query: str) -> str:
    """
    Converts SQLite-style placeholders to PostgreSQL placeholders.

    SQLite:
    ?

    PostgreSQL psycopg:
    %s
    """

    if is_postgres():
        return query.replace("?", "%s")

    return query


def execute_query(cursor: Any, query: str, params: Optional[Any] = None):
    """
    Executes one SQL query with database-compatible placeholders.
    """

    final_query = normalize_query_for_database(query)

    if params is None:
        return cursor.execute(final_query)

    return cursor.execute(final_query, params)


def execute_many(cursor: Any, query: str, params_list: Any):
    """
    Executes many SQL rows with database-compatible placeholders.
    """

    final_query = normalize_query_for_database(query)

    return cursor.executemany(final_query, params_list)


def init_db():
    """
    Initializes database tables and applies lightweight migrations.

    Important:
    CREATE TABLE IF NOT EXISTS does not update old tables.
    So we also run migration helpers to add missing columns.
    """

    if is_postgres():
        _init_postgres_db()
    else:
        _init_sqlite_db()


def _init_sqlite_db():
    conn = _get_sqlite_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS agent_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            request_id TEXT UNIQUE,
            timestamp_utc TEXT,

            user_query TEXT,
            intent TEXT,

            model_name TEXT,
            location_name TEXT,
            date_str TEXT,

            api_url TEXT,
            api_status_code INTEGER,
            api_success INTEGER,
            api_response_json TEXT,

            formatted_response_json TEXT,

            status TEXT,
            error_message TEXT
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS alert_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT UNIQUE,
            generated_at_utc TEXT,

            total_records_received INTEGER,
            total_records_checked INTEGER,
            total_records_skipped INTEGER,

            total_alerts_before_filters INTEGER,
            total_alerts_after_filters INTEGER,
            saved_alert_count INTEGER,

            critical_count INTEGER,
            high_count INTEGER,
            medium_count INTEGER,
            low_count INTEGER,

            filters_json TEXT,
            department_count_json TEXT,
            alert_type_count_json TEXT,

            status TEXT,
            error_message TEXT
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS alert_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT,

            department TEXT,
            severity TEXT,
            alert_type TEXT,

            message TEXT,
            recommendation TEXT,

            reg_num TEXT,
            bike_type TEXT,
            location_name TEXT,

            current_km TEXT,
            next_service_km TEXT,

            force_block TEXT,
            service_alert TEXT,
            booking_status TEXT,

            insurance TEXT,
            emission TEXT,

            alert_json TEXT
        )
        """
    )

    _migrate_sqlite_agent_logs(cursor)
    _migrate_sqlite_alert_runs(cursor)
    _migrate_sqlite_alert_items(cursor)
    _create_sqlite_indexes(cursor)

    conn.commit()
    conn.close()


def _get_sqlite_columns(cursor, table_name: str):
    cursor.execute(f"PRAGMA table_info({table_name})")
    rows = cursor.fetchall()

    return {
        row["name"] if isinstance(row, sqlite3.Row) else row[1]
        for row in rows
    }


def _add_sqlite_column_if_missing(
    cursor,
    table_name: str,
    column_name: str,
    column_definition: str
):
    existing_columns = _get_sqlite_columns(cursor, table_name)

    if column_name not in existing_columns:
        cursor.execute(
            f"""
            ALTER TABLE {table_name}
            ADD COLUMN {column_name} {column_definition}
            """
        )


def _migrate_sqlite_agent_logs(cursor):
    """
    Adds missing columns to old agent_logs tables.

    This fixes errors like:
    table agent_logs has no column named api_response_json
    """

    required_columns = {
        "request_id": "TEXT UNIQUE",
        "timestamp_utc": "TEXT",

        "user_query": "TEXT",
        "intent": "TEXT",

        "model_name": "TEXT",
        "location_name": "TEXT",
        "date_str": "TEXT",

        "api_url": "TEXT",
        "api_status_code": "INTEGER",
        "api_success": "INTEGER",
        "api_response_json": "TEXT",

        "formatted_response_json": "TEXT",

        "status": "TEXT",
        "error_message": "TEXT"
    }

    for column_name, column_definition in required_columns.items():
        _add_sqlite_column_if_missing(
            cursor=cursor,
            table_name="agent_logs",
            column_name=column_name,
            column_definition=column_definition
        )


def _migrate_sqlite_alert_runs(cursor):
    """
    Adds missing columns to old alert_runs tables.
    """

    required_columns = {
        "run_id": "TEXT UNIQUE",
        "generated_at_utc": "TEXT",

        "total_records_received": "INTEGER",
        "total_records_checked": "INTEGER",
        "total_records_skipped": "INTEGER",

        "total_alerts_before_filters": "INTEGER",
        "total_alerts_after_filters": "INTEGER",
        "saved_alert_count": "INTEGER",

        "critical_count": "INTEGER",
        "high_count": "INTEGER",
        "medium_count": "INTEGER",
        "low_count": "INTEGER",

        "filters_json": "TEXT",
        "department_count_json": "TEXT",
        "alert_type_count_json": "TEXT",

        "status": "TEXT",
        "error_message": "TEXT"
    }

    for column_name, column_definition in required_columns.items():
        _add_sqlite_column_if_missing(
            cursor=cursor,
            table_name="alert_runs",
            column_name=column_name,
            column_definition=column_definition
        )


def _migrate_sqlite_alert_items(cursor):
    """
    Adds missing columns to old alert_items tables.
    """

    required_columns = {
        "run_id": "TEXT",

        "department": "TEXT",
        "severity": "TEXT",
        "alert_type": "TEXT",

        "message": "TEXT",
        "recommendation": "TEXT",

        "reg_num": "TEXT",
        "bike_type": "TEXT",
        "location_name": "TEXT",

        "current_km": "TEXT",
        "next_service_km": "TEXT",

        "force_block": "TEXT",
        "service_alert": "TEXT",
        "booking_status": "TEXT",

        "insurance": "TEXT",
        "emission": "TEXT",

        "alert_json": "TEXT"
    }

    for column_name, column_definition in required_columns.items():
        _add_sqlite_column_if_missing(
            cursor=cursor,
            table_name="alert_items",
            column_name=column_name,
            column_definition=column_definition
        )


def _create_sqlite_indexes(cursor):
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_alert_items_run_id
        ON alert_items (run_id)
        """
    )

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_alert_items_department
        ON alert_items (department)
        """
    )

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_alert_items_severity
        ON alert_items (severity)
        """
    )

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_agent_logs_request_id
        ON agent_logs (request_id)
        """
    )


def _init_postgres_db():
    """
    Creates PostgreSQL tables and runs lightweight column migrations.
    """

    conn = _get_postgres_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS agent_logs (
            id BIGSERIAL PRIMARY KEY,
            request_id TEXT UNIQUE,
            timestamp_utc TEXT,

            user_query TEXT,
            intent TEXT,

            model_name TEXT,
            location_name TEXT,
            date_str TEXT,

            api_url TEXT,
            api_status_code INTEGER,
            api_success BOOLEAN,
            api_response_json TEXT,

            formatted_response_json TEXT,

            status TEXT,
            error_message TEXT
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS alert_runs (
            id BIGSERIAL PRIMARY KEY,
            run_id TEXT UNIQUE,
            generated_at_utc TEXT,

            total_records_received INTEGER,
            total_records_checked INTEGER,
            total_records_skipped INTEGER,

            total_alerts_before_filters INTEGER,
            total_alerts_after_filters INTEGER,
            saved_alert_count INTEGER,

            critical_count INTEGER,
            high_count INTEGER,
            medium_count INTEGER,
            low_count INTEGER,

            filters_json TEXT,
            department_count_json TEXT,
            alert_type_count_json TEXT,

            status TEXT,
            error_message TEXT
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS alert_items (
            id BIGSERIAL PRIMARY KEY,
            run_id TEXT,

            department TEXT,
            severity TEXT,
            alert_type TEXT,

            message TEXT,
            recommendation TEXT,

            reg_num TEXT,
            bike_type TEXT,
            location_name TEXT,

            current_km TEXT,
            next_service_km TEXT,

            force_block TEXT,
            service_alert TEXT,
            booking_status TEXT,

            insurance TEXT,
            emission TEXT,

            alert_json TEXT
        )
        """
    )

    _migrate_postgres_tables(cursor)
    _create_postgres_indexes(cursor)

    conn.commit()
    conn.close()


def _add_postgres_column_if_missing(
    cursor,
    table_name: str,
    column_name: str,
    column_definition: str
):
    cursor.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = %s
        AND column_name = %s
        """,
        (table_name, column_name)
    )

    existing = cursor.fetchone()

    if not existing:
        cursor.execute(
            f"""
            ALTER TABLE {table_name}
            ADD COLUMN {column_name} {column_definition}
            """
        )


def _migrate_postgres_tables(cursor):
    agent_log_columns = {
        "request_id": "TEXT UNIQUE",
        "timestamp_utc": "TEXT",
        "user_query": "TEXT",
        "intent": "TEXT",
        "model_name": "TEXT",
        "location_name": "TEXT",
        "date_str": "TEXT",
        "api_url": "TEXT",
        "api_status_code": "INTEGER",
        "api_success": "BOOLEAN",
        "api_response_json": "TEXT",
        "formatted_response_json": "TEXT",
        "status": "TEXT",
        "error_message": "TEXT"
    }

    for column_name, column_definition in agent_log_columns.items():
        _add_postgres_column_if_missing(
            cursor,
            "agent_logs",
            column_name,
            column_definition
        )

    alert_run_columns = {
        "run_id": "TEXT UNIQUE",
        "generated_at_utc": "TEXT",
        "total_records_received": "INTEGER",
        "total_records_checked": "INTEGER",
        "total_records_skipped": "INTEGER",
        "total_alerts_before_filters": "INTEGER",
        "total_alerts_after_filters": "INTEGER",
        "saved_alert_count": "INTEGER",
        "critical_count": "INTEGER",
        "high_count": "INTEGER",
        "medium_count": "INTEGER",
        "low_count": "INTEGER",
        "filters_json": "TEXT",
        "department_count_json": "TEXT",
        "alert_type_count_json": "TEXT",
        "status": "TEXT",
        "error_message": "TEXT"
    }

    for column_name, column_definition in alert_run_columns.items():
        _add_postgres_column_if_missing(
            cursor,
            "alert_runs",
            column_name,
            column_definition
        )

    alert_item_columns = {
        "run_id": "TEXT",
        "department": "TEXT",
        "severity": "TEXT",
        "alert_type": "TEXT",
        "message": "TEXT",
        "recommendation": "TEXT",
        "reg_num": "TEXT",
        "bike_type": "TEXT",
        "location_name": "TEXT",
        "current_km": "TEXT",
        "next_service_km": "TEXT",
        "force_block": "TEXT",
        "service_alert": "TEXT",
        "booking_status": "TEXT",
        "insurance": "TEXT",
        "emission": "TEXT",
        "alert_json": "TEXT"
    }

    for column_name, column_definition in alert_item_columns.items():
        _add_postgres_column_if_missing(
            cursor,
            "alert_items",
            column_name,
            column_definition
        )


def _create_postgres_indexes(cursor):
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_alert_items_run_id
        ON alert_items (run_id)
        """
    )

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_alert_items_department
        ON alert_items (department)
        """
    )

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_alert_items_severity
        ON alert_items (severity)
        """
    )

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_agent_logs_request_id
        ON agent_logs (request_id)
        """
    )
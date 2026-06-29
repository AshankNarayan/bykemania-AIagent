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
    Returns the selected database type.

    Local MVP:
    DATABASE_TYPE=sqlite

    Future cloud:
    DATABASE_TYPE=postgres
    """

    return os.getenv("DATABASE_TYPE", "sqlite").strip().lower()


def get_database_url() -> str:
    """
    Returns DATABASE_URL from .env.

    SQLite examples:
    DATABASE_URL=sqlite:///app/storage/agent_logs.sqlite3
    DATABASE_URL=app/storage/agent_logs.sqlite3

    PostgreSQL example:
    DATABASE_URL=postgresql://username:password@host:5432/database_name
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
    Returns a database connection.

    Current local default:
    - SQLite connection

    Future cloud:
    - PostgreSQL connection using psycopg
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

    This is prepared for the next migration step.

    Important:
    Repository queries still need placeholder compatibility updates
    before switching DATABASE_TYPE=postgres.
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

    SQLite uses:
    ?

    PostgreSQL psycopg uses:
    %s

    Existing repositories currently use '?'.
    In the next step, repositories will call this helper before execution.
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
    Initializes database tables.

    Works for:
    - SQLite now
    - PostgreSQL in the next step after repository compatibility updates
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

    conn.commit()
    conn.close()


def _init_postgres_db():
    """
    Creates PostgreSQL tables.

    This is prepared now, but do not switch DATABASE_TYPE=postgres
    until repositories are updated in the next step.
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

    conn.commit()
    conn.close()
from pathlib import Path
import sqlite3


BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "agent_logs.sqlite3"


def get_connection():
    """
    Creates a new SQLite connection.
    SQLite is enough for MVP because no separate database server is needed.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """
    Creates all required tables:
    1. agent_logs      -> stores chat/query logs
    2. alert_runs      -> stores one alert scan summary
    3. alert_items     -> stores individual alerts from each scan
    """

    conn = get_connection()
    cursor = conn.cursor()

    # Existing query/API logging table
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS agent_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            request_id TEXT UNIQUE NOT NULL,
            timestamp_utc TEXT NOT NULL,

            user_query TEXT NOT NULL,

            intent TEXT,
            model_name TEXT,
            location_name TEXT,
            date_str TEXT,

            api_url TEXT,
            api_params_json TEXT,
            api_status_code INTEGER,
            api_success INTEGER,

            raw_api_response_json TEXT,
            formatted_response_json TEXT,

            status TEXT NOT NULL,
            error_message TEXT,

            feedback_rating INTEGER,
            feedback_note TEXT
        )
        """
    )

    # New table: stores alert run summary
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS alert_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            run_id TEXT UNIQUE NOT NULL,
            generated_at_utc TEXT NOT NULL,

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

            status TEXT NOT NULL,
            error_message TEXT
        )
        """
    )

    # New table: stores individual alert items
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS alert_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            run_id TEXT NOT NULL,

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

            alert_json TEXT,

            FOREIGN KEY (run_id) REFERENCES alert_runs(run_id)
        )
        """
    )

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_alert_items_run_id
        ON alert_items(run_id)
        """
    )

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_alert_items_department
        ON alert_items(department)
        """
    )

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_alert_items_severity
        ON alert_items(severity)
        """
    )

    conn.commit()
    conn.close()
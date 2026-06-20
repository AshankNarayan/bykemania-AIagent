import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from app.storage.database import get_connection, init_db


class AlertRepository:
    """
    Stores alert runs and alert items in SQLite.

    This makes alerts:
    - timestamped
    - dashboard-ready
    - available for history
    - usable later for email automation and analytics
    """

    def __init__(self):
        init_db()

    @staticmethod
    def _to_json(data: Any) -> str:
        try:
            return json.dumps(data, ensure_ascii=False, default=str)
        except Exception:
            return json.dumps({"error": "Could not serialize data"}, ensure_ascii=False)

    @staticmethod
    def _from_json(value: Optional[str]) -> Any:
        if not value:
            return None

        try:
            return json.loads(value)
        except Exception:
            return value

    def save_alert_run_with_items(
        self,
        alert_result: Dict[str, Any],
        alerts_to_save: List[Dict[str, Any]]
    ) -> str:
        """
        Saves one alert run summary and all related alert items.

        Returns:
        - run_id
        """

        run_id = str(uuid4())

        generated_at = alert_result.get(
            "generated_at_utc",
            datetime.now(timezone.utc).isoformat()
        )

        records = alert_result.get("records", {})
        summary = alert_result.get("alerts_summary", {})
        filters = alert_result.get("filters", {})

        severity_count = summary.get("severity_count", {})
        department_count = summary.get("department_count", {})
        alert_type_count = summary.get("alert_type_count", {})

        conn = get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute(
                """
                INSERT INTO alert_runs (
                    run_id,
                    generated_at_utc,

                    total_records_received,
                    total_records_checked,
                    total_records_skipped,

                    total_alerts_before_filters,
                    total_alerts_after_filters,
                    saved_alert_count,

                    critical_count,
                    high_count,
                    medium_count,
                    low_count,

                    filters_json,
                    department_count_json,
                    alert_type_count_json,

                    status,
                    error_message
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    generated_at,

                    records.get("total_records_received"),
                    records.get("total_records_checked"),
                    records.get("total_records_skipped"),

                    summary.get("total_alerts_before_filters"),
                    summary.get("total_alerts_after_filters"),
                    len(alerts_to_save),

                    severity_count.get("critical", 0),
                    severity_count.get("high", 0),
                    severity_count.get("medium", 0),
                    severity_count.get("low", 0),

                    self._to_json(filters),
                    self._to_json(department_count),
                    self._to_json(alert_type_count),

                    "success",
                    None
                )
            )

            alert_rows = []

            for alert in alerts_to_save:
                bike = alert.get("bike", {})

                alert_rows.append(
                    (
                        run_id,

                        alert.get("department"),
                        alert.get("severity"),
                        alert.get("alert_type"),

                        alert.get("message"),
                        alert.get("recommendation"),

                        bike.get("reg_num"),
                        bike.get("bike_type"),
                        bike.get("location_name"),

                        bike.get("current_km"),
                        bike.get("next_service_km"),

                        bike.get("force_block"),
                        bike.get("service_alert"),
                        bike.get("booking_status"),

                        bike.get("insurance"),
                        bike.get("emission"),

                        self._to_json(alert)
                    )
                )

            cursor.executemany(
                """
                INSERT INTO alert_items (
                    run_id,

                    department,
                    severity,
                    alert_type,

                    message,
                    recommendation,

                    reg_num,
                    bike_type,
                    location_name,

                    current_km,
                    next_service_km,

                    force_block,
                    service_alert,
                    booking_status,

                    insurance,
                    emission,

                    alert_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                alert_rows
            )

            conn.commit()

        except Exception:
            conn.rollback()
            raise

        finally:
            conn.close()

        return run_id

    def get_recent_alert_runs(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Returns recent alert run summaries.
        This is useful for dashboard history.
        """

        safe_limit = max(1, min(limit, 100))

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT *
            FROM alert_runs
            ORDER BY id DESC
            LIMIT ?
            """,
            (safe_limit,)
        )

        rows = cursor.fetchall()
        conn.close()

        return [self._format_alert_run_row(row) for row in rows]

    def get_alert_run_by_id(
        self,
        run_id: str,
        limit: int = 100,
        department: Optional[str] = None,
        severity: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Returns one alert run summary + related alert items.
        Supports optional filtering by department and severity.
        """

        safe_limit = max(1, min(limit, 500))

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT *
            FROM alert_runs
            WHERE run_id = ?
            """,
            (run_id,)
        )

        run_row = cursor.fetchone()

        if not run_row:
            conn.close()
            return None

        query = """
            SELECT *
            FROM alert_items
            WHERE run_id = ?
        """

        params: List[Any] = [run_id]

        if department:
            query += " AND LOWER(department) = LOWER(?)"
            params.append(department)

        if severity:
            query += " AND LOWER(severity) = LOWER(?)"
            params.append(severity)

        query += """
            ORDER BY
                CASE severity
                    WHEN 'critical' THEN 1
                    WHEN 'high' THEN 2
                    WHEN 'medium' THEN 3
                    WHEN 'low' THEN 4
                    ELSE 5
                END,
                id ASC
            LIMIT ?
        """

        params.append(safe_limit)

        cursor.execute(query, params)
        item_rows = cursor.fetchall()

        conn.close()

        run_data = self._format_alert_run_row(run_row)

        items = [self._format_alert_item_row(row) for row in item_rows]

        run_data["items"] = items
        run_data["returned_item_count"] = len(items)

        return run_data

    def get_latest_alert_run(
        self,
        limit: int = 100,
        department: Optional[str] = None,
        severity: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Returns the latest saved alert run.
        """

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT run_id
            FROM alert_runs
            ORDER BY id DESC
            LIMIT 1
            """
        )

        row = cursor.fetchone()
        conn.close()

        if not row:
            return None

        return self.get_alert_run_by_id(
            run_id=row["run_id"],
            limit=limit,
            department=department,
            severity=severity
        )

    def _format_alert_run_row(self, row) -> Dict[str, Any]:
        result = dict(row)

        result["filters"] = self._from_json(result.pop("filters_json"))
        result["department_count"] = self._from_json(result.pop("department_count_json"))
        result["alert_type_count"] = self._from_json(result.pop("alert_type_count_json"))

        return result

    def _format_alert_item_row(self, row) -> Dict[str, Any]:
        result = dict(row)

        result["alert"] = self._from_json(result.pop("alert_json"))

        return result
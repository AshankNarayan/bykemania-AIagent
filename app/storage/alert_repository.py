import json
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
from uuid import uuid4

from app.storage.database import get_connection, init_db


class AlertRepository:
    """
    Stores and retrieves alert runs and alert items in SQLite.

    Supports:
    - alert history
    - latest alert run
    - dashboard summary
    - department dashboard cards
    - department-specific dashboard views
    - cooldown checks to prevent duplicate/frequent alert runs
    """

    def __init__(self):
        init_db()

    @staticmethod
    def _to_json(data: Any) -> str:
        try:
            return json.dumps(data, ensure_ascii=False, default=str)
        except Exception:
            return json.dumps(
                {"error": "Could not serialize data"},
                ensure_ascii=False
            )

    @staticmethod
    def _from_json(value: Optional[str]) -> Any:
        if not value:
            return None

        try:
            return json.loads(value)
        except Exception:
            return value

    @staticmethod
    def _parse_iso_datetime(value: Optional[str]) -> Optional[datetime]:
        """
        Parses ISO datetime string safely.
        Handles timezone-aware and naive datetime values.
        """

        if not value:
            return None

        try:
            parsed = datetime.fromisoformat(value)

            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)

            return parsed.astimezone(timezone.utc)

        except Exception:
            return None

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

        Supports optional:
        - department filter
        - severity filter
        - limit
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

    def get_latest_run_id(self) -> Optional[str]:
        """
        Returns latest alert run_id.
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

        return row["run_id"]

    def check_recent_alert_run(
        self,
        cooldown_minutes: int = 30
    ) -> Dict[str, Any]:
        """
        Checks whether a recent alert run already exists.

        If the latest alert run happened within cooldown_minutes,
        a new run should be skipped unless force=true.
        """

        if cooldown_minutes <= 0:
            return {
                "should_skip": False,
                "reason": "Cooldown disabled.",
                "cooldown_minutes": cooldown_minutes,
                "latest_run_id": None,
                "latest_generated_at_utc": None,
                "minutes_since_last_run": None,
                "next_allowed_at_utc": None
            }

        recent_runs = self.get_recent_alert_runs(limit=1)

        if not recent_runs:
            return {
                "should_skip": False,
                "reason": "No previous alert run found.",
                "cooldown_minutes": cooldown_minutes,
                "latest_run_id": None,
                "latest_generated_at_utc": None,
                "minutes_since_last_run": None,
                "next_allowed_at_utc": None
            }

        latest = recent_runs[0]

        latest_generated_at = self._parse_iso_datetime(
            latest.get("generated_at_utc")
        )

        if not latest_generated_at:
            return {
                "should_skip": False,
                "reason": "Could not parse latest alert run timestamp.",
                "cooldown_minutes": cooldown_minutes,
                "latest_run_id": latest.get("run_id"),
                "latest_generated_at_utc": latest.get("generated_at_utc"),
                "minutes_since_last_run": None,
                "next_allowed_at_utc": None
            }

        now = datetime.now(timezone.utc)
        elapsed = now - latest_generated_at
        cooldown = timedelta(minutes=cooldown_minutes)

        minutes_since_last_run = round(elapsed.total_seconds() / 60, 2)
        next_allowed_at = latest_generated_at + cooldown

        should_skip = elapsed < cooldown

        return {
            "should_skip": should_skip,
            "reason": (
                "Latest alert run is still inside cooldown window."
                if should_skip
                else "Cooldown window has passed."
            ),
            "cooldown_minutes": cooldown_minutes,
            "latest_run_id": latest.get("run_id"),
            "latest_generated_at_utc": latest.get("generated_at_utc"),
            "minutes_since_last_run": minutes_since_last_run,
            "next_allowed_at_utc": next_allowed_at.isoformat()
        }

    def get_latest_alert_run(
        self,
        limit: int = 100,
        department: Optional[str] = None,
        severity: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Returns the latest saved alert run.
        """

        latest_run_id = self.get_latest_run_id()

        if not latest_run_id:
            return None

        return self.get_alert_run_by_id(
            run_id=latest_run_id,
            limit=limit,
            department=department,
            severity=severity
        )

    def get_dashboard_summary(self) -> Optional[Dict[str, Any]]:
        """
        Returns clean summary for dashboard home page.
        Does not include individual alert items.
        """

        recent_runs = self.get_recent_alert_runs(limit=1)

        if not recent_runs:
            return None

        latest = recent_runs[0]

        return {
            "run_id": latest.get("run_id"),
            "generated_at_utc": latest.get("generated_at_utc"),
            "status": latest.get("status"),

            "records": {
                "total_records_received": latest.get("total_records_received"),
                "total_records_checked": latest.get("total_records_checked"),
                "total_records_skipped": latest.get("total_records_skipped")
            },

            "alerts": {
                "total_alerts": latest.get("saved_alert_count"),
                "critical": latest.get("critical_count"),
                "high": latest.get("high_count"),
                "medium": latest.get("medium_count"),
                "low": latest.get("low_count")
            },

            "department_count": latest.get("department_count"),
            "alert_type_count": latest.get("alert_type_count")
        }

    def get_department_cards(
        self,
        run_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Returns department-wise dashboard cards.
        """

        if not run_id:
            run_id = self.get_latest_run_id()

        if not run_id:
            return []

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT
                department,
                COUNT(*) AS total_alerts,

                SUM(CASE WHEN severity = 'critical' THEN 1 ELSE 0 END) AS critical,
                SUM(CASE WHEN severity = 'high' THEN 1 ELSE 0 END) AS high,
                SUM(CASE WHEN severity = 'medium' THEN 1 ELSE 0 END) AS medium,
                SUM(CASE WHEN severity = 'low' THEN 1 ELSE 0 END) AS low

            FROM alert_items
            WHERE run_id = ?
            GROUP BY department
            ORDER BY total_alerts DESC
            """,
            (run_id,)
        )

        rows = cursor.fetchall()
        conn.close()

        cards = []

        for row in rows:
            cards.append(
                {
                    "department": row["department"],
                    "total_alerts": row["total_alerts"],
                    "critical": row["critical"] or 0,
                    "high": row["high"] or 0,
                    "medium": row["medium"] or 0,
                    "low": row["low"] or 0
                }
            )

        return cards

    def get_department_dashboard(
        self,
        department_name: str,
        run_id: Optional[str] = None,
        limit: int = 50,
        severity: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Returns dashboard data for one department.
        """

        if not run_id:
            run_id = self.get_latest_run_id()

        if not run_id:
            return None

        safe_limit = max(1, min(limit, 500))

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT
                COUNT(*) AS total_alerts,

                SUM(CASE WHEN severity = 'critical' THEN 1 ELSE 0 END) AS critical,
                SUM(CASE WHEN severity = 'high' THEN 1 ELSE 0 END) AS high,
                SUM(CASE WHEN severity = 'medium' THEN 1 ELSE 0 END) AS medium,
                SUM(CASE WHEN severity = 'low' THEN 1 ELSE 0 END) AS low

            FROM alert_items
            WHERE run_id = ?
            AND LOWER(department) = LOWER(?)
            """,
            (run_id, department_name)
        )

        summary_row = cursor.fetchone()

        if not summary_row or summary_row["total_alerts"] == 0:
            conn.close()

            return {
                "run_id": run_id,
                "department": department_name,
                "summary": {
                    "total_alerts": 0,
                    "critical": 0,
                    "high": 0,
                    "medium": 0,
                    "low": 0
                },
                "alert_type_count": {},
                "items": [],
                "returned_item_count": 0
            }

        cursor.execute(
            """
            SELECT
                alert_type,
                COUNT(*) AS count
            FROM alert_items
            WHERE run_id = ?
            AND LOWER(department) = LOWER(?)
            GROUP BY alert_type
            ORDER BY count DESC
            """,
            (run_id, department_name)
        )

        alert_type_rows = cursor.fetchall()

        alert_type_count = {
            row["alert_type"]: row["count"]
            for row in alert_type_rows
        }

        query = """
            SELECT *
            FROM alert_items
            WHERE run_id = ?
            AND LOWER(department) = LOWER(?)
        """

        params: List[Any] = [run_id, department_name]

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

        items = [self._format_alert_item_row(row) for row in item_rows]

        return {
            "run_id": run_id,
            "department": department_name,
            "filters": {
                "severity": severity,
                "limit": safe_limit
            },
            "summary": {
                "total_alerts": summary_row["total_alerts"],
                "critical": summary_row["critical"] or 0,
                "high": summary_row["high"] or 0,
                "medium": summary_row["medium"] or 0,
                "low": summary_row["low"] or 0
            },
            "alert_type_count": alert_type_count,
            "items": items,
            "returned_item_count": len(items)
        }

    def _format_alert_run_row(self, row) -> Dict[str, Any]:
        result = dict(row)

        result["filters"] = self._from_json(result.pop("filters_json"))
        result["department_count"] = self._from_json(
            result.pop("department_count_json")
        )
        result["alert_type_count"] = self._from_json(
            result.pop("alert_type_count_json")
        )

        return result

    def _format_alert_item_row(self, row) -> Dict[str, Any]:
        result = dict(row)

        result["alert"] = self._from_json(result.pop("alert_json"))

        return result
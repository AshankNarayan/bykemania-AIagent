import json
from datetime import datetime, timezone
from typing import Any, Dict, Optional, List

from app.storage.database import get_connection, init_db


class AgentLogRepository:
    def __init__(self):
        init_db()

    @staticmethod
    def _to_json(data: Any) -> str:
        """
        Safely converts Python data into JSON string.
        default=str prevents datetime or unusual objects from crashing logging.
        """
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

    def create_started_log(self, request_id: str, user_query: str):
        """
        Creates the initial log entry as soon as a query arrives.
        Even if the API fails later, we still have the user query saved.
        """

        timestamp_utc = datetime.now(timezone.utc).isoformat()

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO agent_logs (
                request_id,
                timestamp_utc,
                user_query,
                status
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                request_id,
                timestamp_utc,
                user_query,
                "started"
            )
        )

        conn.commit()
        conn.close()

    def update_after_parse(self, request_id: str, parsed_intent: Dict[str, Any]):
        """
        Saves what the LLM understood from the user query.
        """

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            UPDATE agent_logs
            SET
                intent = ?,
                model_name = ?,
                location_name = ?,
                date_str = ?,
                status = ?
            WHERE request_id = ?
            """,
            (
                parsed_intent.get("intent"),
                parsed_intent.get("model_name"),
                parsed_intent.get("location_name"),
                parsed_intent.get("date_str"),
                "parsed",
                request_id
            )
        )

        conn.commit()
        conn.close()

    def update_after_api(self, request_id: str, api_result: Dict[str, Any]):
        """
        Saves API metadata and raw API response.
        """

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            UPDATE agent_logs
            SET
                api_url = ?,
                api_params_json = ?,
                api_status_code = ?,
                api_success = ?,
                raw_api_response_json = ?,
                status = ?
            WHERE request_id = ?
            """,
            (
                api_result.get("api_url"),
                self._to_json(api_result.get("params")),
                api_result.get("status_code"),
                1 if api_result.get("success") else 0,
                self._to_json(api_result.get("data")),
                "api_completed",
                request_id
            )
        )

        conn.commit()
        conn.close()

    def finish_success(self, request_id: str, formatted_response: Dict[str, Any]):
        """
        Saves the final response shown to the user.
        """

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            UPDATE agent_logs
            SET
                formatted_response_json = ?,
                status = ?,
                error_message = NULL
            WHERE request_id = ?
            """,
            (
                self._to_json(formatted_response),
                "success",
                request_id
            )
        )

        conn.commit()
        conn.close()

    def finish_error(
        self,
        request_id: str,
        error_message: str,
        formatted_response: Optional[Dict[str, Any]] = None
    ):
        """
        Saves error details when something fails.
        """

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            UPDATE agent_logs
            SET
                formatted_response_json = ?,
                status = ?,
                error_message = ?
            WHERE request_id = ?
            """,
            (
                self._to_json(formatted_response) if formatted_response else None,
                "error",
                error_message,
                request_id
            )
        )

        conn.commit()
        conn.close()

    def get_recent_logs(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Returns recent logs without heavy raw API data.
        Useful for dashboard preview.
        """

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT
                id,
                request_id,
                timestamp_utc,
                user_query,
                intent,
                model_name,
                location_name,
                date_str,
                api_status_code,
                api_success,
                status,
                error_message
            FROM agent_logs
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,)
        )

        rows = cursor.fetchall()
        conn.close()

        return [dict(row) for row in rows]

    def get_log_by_request_id(self, request_id: str) -> Optional[Dict[str, Any]]:
        """
        Returns full log for one request.
        This includes raw API response and final response.
        """

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT *
            FROM agent_logs
            WHERE request_id = ?
            """,
            (request_id,)
        )

        row = cursor.fetchone()
        conn.close()

        if not row:
            return None

        result = dict(row)

        result["api_params"] = self._from_json(result.pop("api_params_json"))
        result["raw_api_response"] = self._from_json(result.pop("raw_api_response_json"))
        result["formatted_response"] = self._from_json(result.pop("formatted_response_json"))

        return result
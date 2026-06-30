import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.storage.database import (
    execute_query,
    get_connection,
    init_db
)


class AgentLogRepository:
    """
    Stores and retrieves natural-language query/API logs.

    Compatible with:
    - SQLite
    - PostgreSQL placeholder helper

    Supports the current agent.py lifecycle:
    - create_started_log()
    - update_after_parse()
    - update_after_api()
    - finish_success()
    - finish_error()

    Also keeps older/full methods:
    - save_log()
    - update_completed_log()
    - update_failed_log()
    """

    def __init__(self):
        init_db()

    @staticmethod
    def _now_utc() -> str:
        return datetime.now(timezone.utc).isoformat()

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
    def _row_to_dict(row: Any) -> Dict[str, Any]:
        if row is None:
            return {}

        if isinstance(row, dict):
            return row

        return dict(row)

    @staticmethod
    def _as_dict(value: Any) -> Dict[str, Any]:
        """
        Converts dict / Pydantic model / unknown object into dict safely.
        """

        if value is None:
            return {}

        if isinstance(value, dict):
            return value

        if hasattr(value, "model_dump"):
            try:
                return value.model_dump()
            except Exception:
                return {}

        if hasattr(value, "dict"):
            try:
                return value.dict()
            except Exception:
                return {}

        return {}

    def _ensure_log_exists(
        self,
        cursor,
        request_id: str,
        user_query: str = ""
    ) -> None:
        """
        Ensures a row exists before update methods run.
        """

        execute_query(
            cursor,
            """
            SELECT request_id
            FROM agent_logs
            WHERE request_id = ?
            """,
            (request_id,)
        )

        existing = cursor.fetchone()

        if existing:
            return

        execute_query(
            cursor,
            """
            INSERT INTO agent_logs (
                request_id,
                timestamp_utc,

                user_query,
                intent,

                model_name,
                location_name,
                date_str,

                api_url,
                api_status_code,
                api_success,
                api_response_json,

                formatted_response_json,

                status,
                error_message
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                request_id,
                self._now_utc(),

                user_query,
                None,

                None,
                None,
                None,

                None,
                None,
                None,
                self._to_json({}),

                self._to_json({}),

                "started",
                None
            )
        )

    def create_started_log(
        self,
        request_id: str,
        user_query: Optional[str] = None,
        timestamp_utc: Optional[str] = None,
        parsed_query: Optional[Dict[str, Any]] = None,
        *args,
        **kwargs
    ) -> None:
        """
        Creates or refreshes the first log row when /chat starts.
        """

        user_query = (
            user_query
            or kwargs.get("user_query")
            or kwargs.get("query")
            or ""
        )

        timestamp_utc = (
            timestamp_utc
            or kwargs.get("timestamp_utc")
            or kwargs.get("timestamp")
            or self._now_utc()
        )

        parsed_query = self._as_dict(
            parsed_query
            or kwargs.get("parsed_query")
        )

        conn = get_connection()
        cursor = conn.cursor()

        try:
            self._ensure_log_exists(
                cursor=cursor,
                request_id=request_id,
                user_query=user_query
            )

            execute_query(
                cursor,
                """
                UPDATE agent_logs
                SET
                    timestamp_utc = ?,
                    user_query = ?,
                    intent = ?,
                    model_name = ?,
                    location_name = ?,
                    date_str = ?,
                    status = ?,
                    error_message = ?
                WHERE request_id = ?
                """,
                (
                    timestamp_utc,
                    user_query,
                    parsed_query.get("intent"),
                    parsed_query.get("model_name"),
                    parsed_query.get("location_name"),
                    parsed_query.get("date_str"),
                    "started",
                    None,
                    request_id
                )
            )

            conn.commit()

        except Exception:
            conn.rollback()
            raise

        finally:
            conn.close()

    def update_after_parse(
        self,
        request_id: str,
        parsed_query: Optional[Dict[str, Any]] = None,
        *args,
        **kwargs
    ) -> None:
        """
        Updates log after query parsing.

        Accepts:
        - parsed_query
        - parsed_intent
        - query_intent
        - intent
        """

        parsed_query = self._as_dict(
            parsed_query
            or kwargs.get("parsed_query")
            or kwargs.get("parsed_intent")
            or kwargs.get("query_intent")
            or kwargs.get("intent")
        )

        conn = get_connection()
        cursor = conn.cursor()

        try:
            self._ensure_log_exists(
                cursor=cursor,
                request_id=request_id
            )

            execute_query(
                cursor,
                """
                UPDATE agent_logs
                SET
                    intent = ?,
                    model_name = ?,
                    location_name = ?,
                    date_str = ?,
                    status = ?,
                    error_message = ?
                WHERE request_id = ?
                """,
                (
                    parsed_query.get("intent"),
                    parsed_query.get("model_name"),
                    parsed_query.get("location_name"),
                    parsed_query.get("date_str"),
                    "parsed",
                    None,
                    request_id
                )
            )

            conn.commit()

        except Exception:
            conn.rollback()
            raise

        finally:
            conn.close()

    def update_after_api(
        self,
        request_id: str,
        api_result: Optional[Dict[str, Any]] = None,
        *args,
        **kwargs
    ) -> None:
        """
        Updates log after backend API call.
        """

        api_result = self._as_dict(
            api_result
            or kwargs.get("api_result")
            or kwargs.get("api_response")
        )

        conn = get_connection()
        cursor = conn.cursor()

        try:
            self._ensure_log_exists(
                cursor=cursor,
                request_id=request_id
            )

            execute_query(
                cursor,
                """
                UPDATE agent_logs
                SET
                    api_url = ?,
                    api_status_code = ?,
                    api_success = ?,
                    api_response_json = ?,
                    status = ?,
                    error_message = ?
                WHERE request_id = ?
                """,
                (
                    api_result.get("api_url") or api_result.get("url"),
                    api_result.get("status_code"),
                    bool(api_result.get("success", False)),
                    self._to_json(api_result),
                    "api_completed",
                    None,
                    request_id
                )
            )

            conn.commit()

        except Exception:
            conn.rollback()
            raise

        finally:
            conn.close()

    def finish_success(
        self,
        request_id: str,
        formatted_response: Optional[Dict[str, Any]] = None,
        *args,
        **kwargs
    ) -> None:
        """
        Marks log as successful after final response formatting.
        """

        formatted_response = self._as_dict(
            formatted_response
            or kwargs.get("formatted_response")
            or kwargs.get("response")
            or kwargs.get("response_data")
            or kwargs.get("final_response")
        )

        conn = get_connection()
        cursor = conn.cursor()

        try:
            self._ensure_log_exists(
                cursor=cursor,
                request_id=request_id
            )

            execute_query(
                cursor,
                """
                UPDATE agent_logs
                SET
                    formatted_response_json = ?,
                    status = ?,
                    error_message = ?
                WHERE request_id = ?
                """,
                (
                    self._to_json(formatted_response),
                    "success",
                    None,
                    request_id
                )
            )

            conn.commit()

        except Exception:
            conn.rollback()
            raise

        finally:
            conn.close()

    def finish_error(
        self,
        request_id: str,
        error_message: Optional[str] = None,
        parsed_query: Optional[Dict[str, Any]] = None,
        api_result: Optional[Dict[str, Any]] = None,
        formatted_response: Optional[Dict[str, Any]] = None,
        *args,
        **kwargs
    ) -> None:
        """
        Marks log as failed.
        """

        error_message = (
            error_message
            or kwargs.get("error_message")
            or kwargs.get("error")
            or "Unknown error"
        )

        parsed_query = self._as_dict(
            parsed_query
            or kwargs.get("parsed_query")
            or kwargs.get("parsed_intent")
        )

        api_result = self._as_dict(
            api_result
            or kwargs.get("api_result")
            or kwargs.get("api_response")
        )

        formatted_response = self._as_dict(
            formatted_response
            or kwargs.get("formatted_response")
            or kwargs.get("response")
            or kwargs.get("response_data")
            or {
                "summary": "Request failed.",
                "error": error_message
            }
        )

        conn = get_connection()
        cursor = conn.cursor()

        try:
            self._ensure_log_exists(
                cursor=cursor,
                request_id=request_id
            )

            execute_query(
                cursor,
                """
                UPDATE agent_logs
                SET
                    intent = COALESCE(?, intent),
                    model_name = COALESCE(?, model_name),
                    location_name = COALESCE(?, location_name),
                    date_str = COALESCE(?, date_str),

                    api_url = COALESCE(?, api_url),
                    api_status_code = COALESCE(?, api_status_code),
                    api_success = ?,
                    api_response_json = ?,

                    formatted_response_json = ?,

                    status = ?,
                    error_message = ?
                WHERE request_id = ?
                """,
                (
                    parsed_query.get("intent"),
                    parsed_query.get("model_name"),
                    parsed_query.get("location_name"),
                    parsed_query.get("date_str"),

                    api_result.get("api_url") or api_result.get("url"),
                    api_result.get("status_code"),
                    bool(api_result.get("success", False)) if api_result else False,
                    self._to_json(api_result),

                    self._to_json(formatted_response),

                    "error",
                    str(error_message),
                    request_id
                )
            )

            conn.commit()

        except Exception:
            conn.rollback()
            raise

        finally:
            conn.close()

    def update_completed_log(
        self,
        request_id: str,
        parsed_query: Optional[Dict[str, Any]] = None,
        api_result: Optional[Dict[str, Any]] = None,
        formatted_response: Optional[Dict[str, Any]] = None,
        *args,
        **kwargs
    ) -> None:
        """
        Backward-compatible method for older code.
        """

        self.update_after_parse(
            request_id=request_id,
            parsed_query=(
                parsed_query
                or kwargs.get("parsed_query")
                or kwargs.get("parsed_intent")
            )
        )

        self.update_after_api(
            request_id=request_id,
            api_result=api_result or kwargs.get("api_result")
        )

        self.finish_success(
            request_id=request_id,
            formatted_response=(
                formatted_response
                or kwargs.get("formatted_response")
                or kwargs.get("response")
            )
        )

    def update_failed_log(
        self,
        request_id: str,
        error_message: Optional[str] = None,
        parsed_query: Optional[Dict[str, Any]] = None,
        api_result: Optional[Dict[str, Any]] = None,
        formatted_response: Optional[Dict[str, Any]] = None,
        *args,
        **kwargs
    ) -> None:
        """
        Backward-compatible method for older code.
        """

        self.finish_error(
            request_id=request_id,
            error_message=error_message or kwargs.get("error_message"),
            parsed_query=(
                parsed_query
                or kwargs.get("parsed_query")
                or kwargs.get("parsed_intent")
            ),
            api_result=api_result or kwargs.get("api_result"),
            formatted_response=(
                formatted_response
                or kwargs.get("formatted_response")
                or kwargs.get("response")
            )
        )

    def save_log(
        self,
        request_id: str,
        timestamp_utc: str,
        user_query: str,
        parsed_query: Dict[str, Any],
        api_result: Dict[str, Any],
        formatted_response: Dict[str, Any],
        status: str = "success",
        error_message: Optional[str] = None
    ) -> None:
        """
        Saves one complete query/API log directly.
        """

        parsed_query = self._as_dict(parsed_query)
        api_result = self._as_dict(api_result)
        formatted_response = self._as_dict(formatted_response)

        conn = get_connection()
        cursor = conn.cursor()

        try:
            self._ensure_log_exists(
                cursor=cursor,
                request_id=request_id,
                user_query=user_query
            )

            execute_query(
                cursor,
                """
                UPDATE agent_logs
                SET
                    timestamp_utc = ?,
                    user_query = ?,

                    intent = ?,
                    model_name = ?,
                    location_name = ?,
                    date_str = ?,

                    api_url = ?,
                    api_status_code = ?,
                    api_success = ?,
                    api_response_json = ?,

                    formatted_response_json = ?,

                    status = ?,
                    error_message = ?
                WHERE request_id = ?
                """,
                (
                    timestamp_utc,
                    user_query,

                    parsed_query.get("intent"),
                    parsed_query.get("model_name"),
                    parsed_query.get("location_name"),
                    parsed_query.get("date_str"),

                    api_result.get("api_url") or api_result.get("url"),
                    api_result.get("status_code"),
                    bool(api_result.get("success", False)),
                    self._to_json(api_result),

                    self._to_json(formatted_response),

                    status,
                    error_message,
                    request_id
                )
            )

            conn.commit()

        except Exception:
            conn.rollback()
            raise

        finally:
            conn.close()

    def get_recent_logs(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Returns recent query logs without large raw API JSON payloads.
        """

        safe_limit = max(1, min(limit, 100))

        conn = get_connection()
        cursor = conn.cursor()

        execute_query(
            cursor,
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

                api_url,
                api_status_code,
                api_success,

                status,
                error_message
            FROM agent_logs
            ORDER BY id DESC
            LIMIT ?
            """,
            (safe_limit,)
        )

        rows = cursor.fetchall()
        conn.close()

        return [self._format_recent_log_row(row) for row in rows]

    def get_log_by_request_id(
        self,
        request_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Returns one full query log including raw API response JSON
        and formatted response JSON.
        """

        conn = get_connection()
        cursor = conn.cursor()

        execute_query(
            cursor,
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

        return self._format_full_log_row(row)

    def _format_recent_log_row(self, row: Any) -> Dict[str, Any]:
        result = self._row_to_dict(row)

        result["api_success"] = bool(result.get("api_success"))

        return result

    def _format_full_log_row(self, row: Any) -> Dict[str, Any]:
        result = self._row_to_dict(row)

        result["api_success"] = bool(result.get("api_success"))

        result["api_response"] = self._from_json(
            result.pop("api_response_json", None)
        )

        result["formatted_response"] = self._from_json(
            result.pop("formatted_response_json", None)
        )

        return result
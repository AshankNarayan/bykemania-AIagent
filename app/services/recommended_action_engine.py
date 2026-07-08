from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


class RecommendedActionEngine:
    """
    Converts operational alerts into clear recommended actions.

    Current mode:
    - recommendation-only
    - no write actions
    - no bike status update
    - no task creation

    Future mode after write APIs:
    - create maintenance task
    - update bike status
    - notify admin/team
    """

    def __init__(self):
        self.severity_score = {
            "critical": 100,
            "high": 75,
            "medium": 45,
            "low": 20,
        }

    def _now_utc(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _safe_str(self, value: Any, fallback: str = "-") -> str:
        if value is None:
            return fallback

        text = str(value).strip()

        if not text:
            return fallback

        return text

    def _safe_int(self, value: Any, fallback: int = 0) -> int:
        try:
            if value is None or value == "":
                return fallback

            return int(float(str(value).replace(",", "").strip()))
        except Exception:
            return fallback

    def _pick(self, source: Dict[str, Any], keys: List[str], fallback: Any = None) -> Any:
        if not isinstance(source, dict):
            return fallback

        for key in keys:
            if "." in key:
                current: Any = source

                for part in key.split("."):
                    if not isinstance(current, dict) or part not in current:
                        current = None
                        break

                    current = current.get(part)

                if current not in [None, ""]:
                    return current
            else:
                value = source.get(key)

                if value not in [None, ""]:
                    return value

        return fallback

    def _format_label(self, value: Any) -> str:
        text = self._safe_str(value, "Unknown")

        return (
            text.replace("_", " ")
            .replace("-", " ")
            .title()
        )

    def _get_alert_items(self, latest_alert_run: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not isinstance(latest_alert_run, dict):
            return []

        payload = (
            latest_alert_run.get("latest_alert_run")
            or latest_alert_run.get("alert_run")
            or latest_alert_run
        )

        possible_items = (
            payload.get("items")
            or payload.get("alerts")
            or payload.get("alert_items")
            or payload.get("data")
            or payload.get("details")
            or []
        )

        if not isinstance(possible_items, list):
            return []

        return [
            item for item in possible_items
            if isinstance(item, dict)
        ]

    def _extract_vehicle(self, alert: Dict[str, Any]) -> str:
        direct_value = self._pick(
            alert,
            [
                "vehicle_number",
                "vehicle_no",
                "registration_number",
                "registration_no",
                "reg_no",
                "reg_number",
                "vehicle_reg_no",
                "bike_number",
                "bike_no",
                "number_plate",
                "vehicle_id",
                "bike_id",
                "bike.reg_num",
                "bike.registration_number",
                "bike.reg_no",
                "metadata.vehicle_number",
                "metadata.registration_number",
                "metadata.reg_no",
            ],
            "",
        )

        if direct_value:
            return self._safe_str(direct_value)

        message = self._safe_str(
            self._pick(alert, ["message", "description", "reason"], ""),
            "",
        )

        first_word = message.split(" ")[0].strip() if message else ""

        if 6 <= len(first_word) <= 14:
            return first_word

        return "-"

    def _normalize_alert(self, alert: Dict[str, Any]) -> Dict[str, Any]:
        severity = self._safe_str(
            self._pick(alert, ["severity", "priority"], "medium"),
            "medium",
        ).lower()

        department = self._safe_str(
            self._pick(
                alert,
                [
                    "department",
                    "department_name",
                    "source_department",
                    "alert_department",
                ],
                "Unknown Department",
            ),
            "Unknown Department",
        )

        alert_type = self._safe_str(
            self._pick(
                alert,
                [
                    "alert_type",
                    "type",
                    "category",
                    "alert_category",
                ],
                "UNKNOWN_ALERT",
            ),
            "UNKNOWN_ALERT",
        )

        location = self._safe_str(
            self._pick(
                alert,
                [
                    "location",
                    "location_name",
                    "branch",
                    "station",
                    "bike.location_name",
                    "metadata.location_name",
                ],
                "-",
            )
        )

        message = self._safe_str(
            self._pick(
                alert,
                [
                    "message",
                    "description",
                    "reason",
                    "title",
                    "alert_message",
                ],
                "-",
            )
        )

        return {
            "severity": severity,
            "department": department,
            "alert_type": alert_type,
            "alert_type_display": self._format_label(alert_type),
            "vehicle": self._extract_vehicle(alert),
            "location": location,
            "message": message,
            "risk_score": self.severity_score.get(severity, 30),
        }

    def _detect_owner(self, alert: Dict[str, Any]) -> str:
        department = alert["department"].lower()
        alert_type = alert["alert_type"].lower()
        message = alert["message"].lower()

        if "compliance" in department or "insurance" in message or "document" in message:
            return "Compliance Team"

        if "service" in department or "service" in alert_type or "maintenance" in message:
            return "Service Team"

        if "recovery" in department or "recovery" in alert_type:
            return "Recovery Team"

        if "fleet" in department or "block" in alert_type or "blocked" in message:
            return "Fleet Operations"

        return "Operations Admin"

    def _build_action_for_alert(self, alert: Dict[str, Any]) -> Dict[str, Any]:
        owner = self._detect_owner(alert)

        department = alert["department"].lower()
        alert_type = alert["alert_type"].lower()
        message = alert["message"].lower()

        title = "Review operational alert"
        suggested_action = "Review this alert manually and keep the vehicle unavailable until resolved."
        action_type = "manual_review"

        if "compliance" in department or "insurance" in message or "document" in message:
            title = "Verify compliance before rental"
            suggested_action = (
                "Keep the vehicle blocked until document, insurance, or compliance status is verified."
            )
            action_type = "compliance_review"

        elif "service" in department or "service" in alert_type or "maintenance" in message:
            title = "Assign service inspection"
            suggested_action = (
                "Send the vehicle for service inspection and mark it unavailable until cleared."
            )
            action_type = "service_inspection"

        elif "recovery" in department or "recovery" in alert_type:
            title = "Assign recovery follow-up"
            suggested_action = (
                "Assign recovery follow-up and do not rent the vehicle until recovery status is resolved."
            )
            action_type = "recovery_follow_up"

        elif "force block" in alert_type or "force blocked" in message or "blocked" in message:
            title = "Review blocked vehicle"
            suggested_action = (
                "Review the block reason and unblock only after manual operations approval."
            )
            action_type = "block_status_review"

        return {
            "priority": alert["severity"],
            "risk_score": alert["risk_score"],
            "owner": owner,
            "department": alert["department"],
            "action_type": action_type,
            "title": title,
            "vehicle": alert["vehicle"],
            "location": alert["location"],
            "alert_type": alert["alert_type"],
            "alert_type_display": alert["alert_type_display"],
            "reason": alert["message"],
            "suggested_action": suggested_action,
            "can_execute_now": False,
            "execution_status": "recommendation_only",
            "requires_confirmation": True,
        }

    def _build_counts(self, actions: List[Dict[str, Any]], key: str) -> List[Dict[str, Any]]:
        counts: Dict[str, int] = {}

        for action in actions:
            value = self._safe_str(action.get(key), "Unknown")
            counts[value] = counts.get(value, 0) + 1

        return [
            {
                key: item_key,
                "display_name": self._format_label(item_key),
                "count": count,
            }
            for item_key, count in sorted(
                counts.items(),
                key=lambda item: item[1],
                reverse=True,
            )
        ]

    def _build_summary(self, actions: List[Dict[str, Any]]) -> str:
        if not actions:
            return "No recommended actions could be generated from the latest saved alert run."

        critical_count = sum(1 for action in actions if action["priority"] == "critical")
        high_count = sum(1 for action in actions if action["priority"] == "high")

        owner_counts = self._build_counts(actions, "owner")
        top_owner = owner_counts[0]["display_name"] if owner_counts else "Operations Admin"

        return (
            f"Generated {len(actions)} recommended actions from the latest alert data. "
            f"{critical_count} are critical and {high_count} are high priority. "
            f"The team needing the most attention is {top_owner}. "
            "These are recommendation-only actions until write APIs are connected."
        )

    def generate(
        self,
        latest_alert_run: Optional[Dict[str, Any]],
        limit: int = 25,
        department: Optional[str] = None,
        severity: Optional[str] = None,
    ) -> Dict[str, Any]:
        safe_limit = max(1, min(limit, 100))

        raw_alerts = self._get_alert_items(latest_alert_run)

        normalized_alerts = [
            self._normalize_alert(alert)
            for alert in raw_alerts
        ]

        if department:
            department_query = department.lower().strip()
            normalized_alerts = [
                alert for alert in normalized_alerts
                if department_query in alert["department"].lower()
            ]

        if severity:
            severity_query = severity.lower().strip()
            normalized_alerts = [
                alert for alert in normalized_alerts
                if alert["severity"].lower() == severity_query
            ]

        actions = [
            self._build_action_for_alert(alert)
            for alert in normalized_alerts
        ]

        actions = sorted(
            actions,
            key=lambda item: item["risk_score"],
            reverse=True,
        )

        visible_actions = actions[:safe_limit]

        return {
            "answer_type": "recommended_actions",
            "summary": self._build_summary(actions),
            "total_actions": len(actions),
            "returned_actions": len(visible_actions),
            "owner_breakdown": self._build_counts(actions, "owner"),
            "department_breakdown": self._build_counts(actions, "department"),
            "action_type_breakdown": self._build_counts(actions, "action_type"),
            "recommended_actions": visible_actions,
            "execution_mode": {
                "can_execute_actions": False,
                "reason": "Write APIs for task creation, bike status updates, and notifications are not connected yet.",
                "future_required_apis": [
                    "maintenance_task_creation_api",
                    "bike_status_update_api",
                    "admin_notification_api",
                ],
            },
            "generated_at": self._now_utc(),
        }
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


class CriticalAlertsService:
    """
    Builds a focused Critical Alerts view from the latest saved alert run.

    Purpose:
    - show urgent vehicles/issues first
    - group critical alerts by department and type
    - suggest basic operational actions
    """

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

        parts = message.split(" ")

        if parts:
            first_word = parts[0].strip()

            if 6 <= len(first_word) <= 14:
                return first_word

        return "-"

    def _get_department(self, alert: Dict[str, Any]) -> str:
        return self._safe_str(
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

    def _get_alert_type(self, alert: Dict[str, Any]) -> str:
        return self._safe_str(
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

    def _get_location(self, alert: Dict[str, Any]) -> str:
        return self._safe_str(
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

    def _get_message(self, alert: Dict[str, Any]) -> str:
        return self._safe_str(
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

    def _get_recommendation(self, alert: Dict[str, Any]) -> str:
        direct_recommendation = self._pick(
            alert,
            [
                "recommendation",
                "suggested_action",
                "action",
            ],
            "",
        )

        if direct_recommendation:
            return self._safe_str(direct_recommendation)

        department = self._get_department(alert).lower()
        alert_type = self._get_alert_type(alert).lower()
        message = self._get_message(alert).lower()

        if "compliance" in department or "insurance" in message or "document" in message:
            return "Keep this vehicle blocked until documents/compliance status are verified."

        if "service" in department or "service" in alert_type or "maintenance" in message:
            return "Assign service inspection and keep the vehicle unavailable until cleared."

        if "recovery" in department or "recovery" in alert_type:
            return "Assign recovery follow-up and do not rent this vehicle until recovery status is resolved."

        if "force block" in alert_type or "force blocked" in message:
            return "Review force-block reason and unblock only after manual operations approval."

        return "Review this alert manually and keep the vehicle unavailable until resolved."

    def _normalize_alert(self, alert: Dict[str, Any]) -> Dict[str, Any]:
        severity = self._safe_str(
            self._pick(alert, ["severity", "priority"], "critical"),
            "critical",
        )

        alert_type = self._get_alert_type(alert)
        department = self._get_department(alert)

        return {
            "severity": severity.lower(),
            "department": department,
            "alert_type": alert_type,
            "alert_type_display": self._format_label(alert_type),
            "vehicle": self._extract_vehicle(alert),
            "location": self._get_location(alert),
            "message": self._get_message(alert),
            "recommendation": self._get_recommendation(alert),
        }

    def _build_counts(self, alerts: List[Dict[str, Any]], key: str) -> List[Dict[str, Any]]:
        counts: Dict[str, int] = {}

        for alert in alerts:
            value = self._safe_str(alert.get(key), "Unknown")
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

    def _build_summary(
        self,
        total_critical: int,
        department_counts: List[Dict[str, Any]],
        alert_type_counts: List[Dict[str, Any]],
    ) -> str:
        if total_critical == 0:
            return "No critical alerts were found in the latest saved alert run."

        top_department = (
            department_counts[0]["display_name"]
            if department_counts
            else "Unknown Department"
        )

        top_type = (
            alert_type_counts[0]["display_name"]
            if alert_type_counts
            else "Unknown Alert Type"
        )

        return (
            f"There are {total_critical} critical alerts in the latest alert sample. "
            f"The highest-risk department is {top_department}, and the most common "
            f"critical issue type is {top_type}. These should be reviewed before "
            "vehicles are made available for rental."
        )

    def generate(
        self,
        latest_alert_run: Optional[Dict[str, Any]],
        limit: int = 25,
    ) -> Dict[str, Any]:
        safe_limit = max(1, min(limit, 100))

        raw_alerts = self._get_alert_items(latest_alert_run)

        normalized_alerts = [
            self._normalize_alert(alert)
            for alert in raw_alerts
        ]

        critical_alerts = [
            alert for alert in normalized_alerts
            if alert.get("severity", "").lower() == "critical"
        ]

        if not critical_alerts and normalized_alerts:
            critical_alerts = normalized_alerts

        visible_alerts = critical_alerts[:safe_limit]

        department_counts = self._build_counts(
            alerts=critical_alerts,
            key="department",
        )

        alert_type_counts = self._build_counts(
            alerts=critical_alerts,
            key="alert_type",
        )

        return {
            "answer_type": "critical_alerts",
            "summary": self._build_summary(
                total_critical=len(critical_alerts),
                department_counts=department_counts,
                alert_type_counts=alert_type_counts,
            ),
            "total_critical_alerts": len(critical_alerts),
            "returned_alerts": len(visible_alerts),
            "department_breakdown": department_counts,
            "alert_type_breakdown": alert_type_counts,
            "critical_alerts": visible_alerts,
            "recommended_actions": [
                {
                    "priority": "critical",
                    "title": "Review critical vehicles before rental",
                    "action": "Keep critical vehicles blocked until the department owner resolves the alert.",
                },
                {
                    "priority": "high",
                    "title": "Assign department ownership",
                    "action": "Group critical alerts by department and assign each group to the responsible team.",
                },
                {
                    "priority": "high",
                    "title": "Resolve repeated alert types first",
                    "action": "Focus on the most frequent critical alert type to reduce operational risk quickly.",
                },
            ],
            "generated_at": self._now_utc(),
        }
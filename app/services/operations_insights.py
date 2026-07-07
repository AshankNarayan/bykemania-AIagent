from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


class OperationsInsightsService:
    """
    Generates Today's AI Insights using existing BykeMania data.

    Uses:
    - dashboard summary
    - department cards
    - latest alert run
    - latest alert items

    Does NOT require extra APIs.
    """

    def __init__(self):
        self.severity_priority = {
            "critical": 1,
            "high": 2,
            "medium": 3,
            "low": 4,
        }

    def _now_utc(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _safe_str(self, value: Any, fallback: str = "") -> str:
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

    def _get_dashboard_payload(self, dashboard_summary: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        if not isinstance(dashboard_summary, dict):
            return {}

        return (
            dashboard_summary.get("dashboard")
            or dashboard_summary.get("summary")
            or dashboard_summary.get("data")
            or dashboard_summary
        )

    def _get_latest_payload(self, latest_alert_run: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        if not isinstance(latest_alert_run, dict):
            return {}

        return (
            latest_alert_run.get("latest_alert_run")
            or latest_alert_run.get("alert_run")
            or latest_alert_run
        )

    def _get_alert_items(self, latest_payload: Dict[str, Any]) -> List[Dict[str, Any]]:
        possible_items = (
            latest_payload.get("items")
            or latest_payload.get("alerts")
            or latest_payload.get("alert_items")
            or latest_payload.get("data")
            or latest_payload.get("details")
            or []
        )

        if isinstance(possible_items, list):
            return [
                item for item in possible_items
                if isinstance(item, dict)
            ]

        return []

    def _get_department_name(self, department: Dict[str, Any]) -> str:
        return self._safe_str(
            self._pick(
                department,
                [
                    "department",
                    "department_name",
                    "name",
                    "title",
                ],
                "Unknown Department",
            ),
            "Unknown Department",
        )

    def _get_department_total(self, department: Dict[str, Any]) -> int:
        summary = department.get("summary") if isinstance(department.get("summary"), dict) else department

        return self._safe_int(
            self._pick(
                summary,
                [
                    "total_alerts",
                    "alert_count",
                    "count",
                    "total",
                    "total_items",
                ],
                0,
            )
        )

    def _get_department_severity(self, department: Dict[str, Any], severity: str) -> int:
        summary = department.get("summary") if isinstance(department.get("summary"), dict) else department
        lower = severity.lower()
        upper = severity.upper()

        return self._safe_int(
            self._pick(
                summary,
                [
                    lower,
                    upper,
                    f"{lower}_count",
                    f"{upper}_count",
                    f"severity.{lower}",
                    f"severity.{upper}",
                    f"summary.{lower}",
                    f"summary.{upper}",
                    f"summary.{lower}_count",
                    f"summary.{upper}_count",
                ],
                0,
            )
        )

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
                "bike.reg_num",
                "bike.registration_number",
                "bike.reg_no",
            ],
            "",
        )

        if direct_value:
            return self._safe_str(direct_value, "-")

        message = self._safe_str(
            self._pick(alert, ["message", "description", "reason"], "")
        )

        parts = message.split(" ")

        if parts:
            first_word = parts[0].strip()

            if 6 <= len(first_word) <= 14:
                return first_word

        return "-"

    def _sort_alerts(self, alerts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return sorted(
            alerts,
            key=lambda item: self.severity_priority.get(
                self._safe_str(item.get("severity"), "low").lower(),
                99,
            ),
        )

    def _build_department_rankings(
        self,
        department_cards: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        rankings = []

        for department in department_cards:
            if not isinstance(department, dict):
                continue

            total_alerts = self._get_department_total(department)

            rankings.append(
                {
                    "department": self._get_department_name(department),
                    "total_alerts": total_alerts,
                    "critical": self._get_department_severity(department, "critical"),
                    "high": self._get_department_severity(department, "high"),
                    "medium": self._get_department_severity(department, "medium"),
                    "low": self._get_department_severity(department, "low"),
                }
            )

        return sorted(
            rankings,
            key=lambda item: (
                item["critical"],
                item["high"],
                item["total_alerts"],
            ),
            reverse=True,
        )

    def _build_alert_type_counts(
        self,
        latest_payload: Dict[str, Any],
        alerts: List[Dict[str, Any]]
    ) -> Dict[str, int]:
        direct_counts = (
            latest_payload.get("alert_type_count")
            or latest_payload.get("alertTypeCount")
            or latest_payload.get("type_count")
            or latest_payload.get("types")
            or latest_payload.get("summary", {}).get("alert_type_count")
            if isinstance(latest_payload.get("summary"), dict)
            else None
        )

        if isinstance(direct_counts, dict):
            return {
                str(key): self._safe_int(value)
                for key, value in direct_counts.items()
            }

        counts: Dict[str, int] = {}

        for alert in alerts:
            alert_type = self._safe_str(
                self._pick(
                    alert,
                    ["alert_type", "type", "category"],
                    "UNKNOWN_ALERT",
                ),
                "UNKNOWN_ALERT",
            )

            counts[alert_type] = counts.get(alert_type, 0) + 1

        return counts

    def _build_top_alert_types(self, alert_type_counts: Dict[str, int]) -> List[Dict[str, Any]]:
        return [
            {
                "alert_type": alert_type,
                "display_name": self._format_label(alert_type),
                "count": count,
            }
            for alert_type, count in sorted(
                alert_type_counts.items(),
                key=lambda item: item[1],
                reverse=True,
            )
        ]

    def _build_recommended_actions(
        self,
        department_rankings: List[Dict[str, Any]],
        top_alert_types: List[Dict[str, Any]],
        critical_alerts: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        actions: List[Dict[str, Any]] = []

        if department_rankings:
            top_department = department_rankings[0]

            actions.append(
                {
                    "priority": "high",
                    "title": f"Prioritize {top_department['department']}",
                    "reason": (
                        f"This department currently has {top_department['total_alerts']} alerts, "
                        f"including {top_department['critical']} critical and "
                        f"{top_department['high']} high severity alerts."
                    ),
                    "suggested_action": (
                        "Assign an operations owner to review and close the highest severity items first."
                    ),
                }
            )

        if top_alert_types:
            top_type = top_alert_types[0]

            actions.append(
                {
                    "priority": "high",
                    "title": f"Reduce {top_type['display_name']} alerts",
                    "reason": (
                        f"This is the most common alert type right now with {top_type['count']} cases."
                    ),
                    "suggested_action": (
                        "Group these alerts by location/model and resolve the repeated root cause."
                    ),
                }
            )

        if critical_alerts:
            actions.append(
                {
                    "priority": "critical",
                    "title": "Review critical vehicles before rental",
                    "reason": (
                        f"There are {len(critical_alerts)} critical alert items in the current sample."
                    ),
                    "suggested_action": (
                        "Keep these vehicles blocked until service/compliance/recovery checks are completed."
                    ),
                }
            )

        actions.append(
            {
                "priority": "medium",
                "title": "Use current insights as operational guidance only",
                "reason": (
                    "Demand, revenue, and customer complaint data are not connected yet."
                ),
                "suggested_action": (
                    "Use this dashboard for fleet health and alert prioritization until additional APIs are added."
                ),
            }
        )

        return actions

    def _build_summary_text(
        self,
        total_alerts: int,
        critical_count: int,
        high_count: int,
        department_rankings: List[Dict[str, Any]],
        top_alert_types: List[Dict[str, Any]],
    ) -> str:
        if not department_rankings and not top_alert_types:
            return (
                "No saved alert insights were found yet. Run an alert scan first, then reload insights."
            )

        top_department_text = "no clear top department"
        top_alert_type_text = "no clear top alert type"

        if department_rankings:
            top_department = department_rankings[0]
            top_department_text = (
                f"{top_department['department']} with {top_department['total_alerts']} alerts"
            )

        if top_alert_types:
            top_alert = top_alert_types[0]
            top_alert_type_text = (
                f"{top_alert['display_name']} with {top_alert['count']} cases"
            )

        return (
            f"Today's operations risk is led by {top_department_text}. "
            f"The most common alert pattern is {top_alert_type_text}. "
            f"Overall alert volume is {total_alerts}, with {critical_count} critical "
            f"and {high_count} high severity alerts. The team should prioritize "
            "critical compliance/service/recovery issues before improving fleet availability."
        )

    def generate(
        self,
        dashboard_summary: Optional[Dict[str, Any]] = None,
        department_cards: Optional[List[Dict[str, Any]]] = None,
        latest_alert_run: Optional[Dict[str, Any]] = None,
        limit: int = 10,
    ) -> Dict[str, Any]:
        safe_limit = max(1, min(limit, 50))

        department_cards = department_cards or []

        dashboard_payload = self._get_dashboard_payload(dashboard_summary)
        latest_payload = self._get_latest_payload(latest_alert_run)

        alerts = self._get_alert_items(latest_payload)
        sorted_alerts = self._sort_alerts(alerts)

        department_rankings = self._build_department_rankings(department_cards)
        alert_type_counts = self._build_alert_type_counts(latest_payload, alerts)
        top_alert_types = self._build_top_alert_types(alert_type_counts)

        total_alerts_from_departments = sum(
            item["total_alerts"] for item in department_rankings
        )

        total_alerts = self._safe_int(
            self._pick(
                dashboard_payload,
                [
                    "total_alerts",
                    "alert_count",
                    "alerts_count",
                    "total",
                    "summary.total_alerts",
                    "latest_alert_run.total_alerts",
                ],
                0,
            )
        ) or total_alerts_from_departments

        critical_count = sum(item["critical"] for item in department_rankings)
        high_count = sum(item["high"] for item in department_rankings)
        medium_count = sum(item["medium"] for item in department_rankings)
        low_count = sum(item["low"] for item in department_rankings)

        critical_alerts = [
            alert for alert in sorted_alerts
            if self._safe_str(alert.get("severity")).lower() == "critical"
        ][:safe_limit]

        high_alerts = [
            alert for alert in sorted_alerts
            if self._safe_str(alert.get("severity")).lower() == "high"
        ][:safe_limit]

        top_critical_alerts = []

        for alert in critical_alerts:
            top_critical_alerts.append(
                {
                    "severity": self._safe_str(alert.get("severity"), "-"),
                    "department": self._safe_str(alert.get("department"), "-"),
                    "alert_type": self._safe_str(
                        self._pick(alert, ["alert_type", "type", "category"], "-")
                    ),
                    "vehicle": self._extract_vehicle(alert),
                    "location": self._safe_str(
                        self._pick(
                            alert,
                            [
                                "location",
                                "location_name",
                                "branch",
                                "station",
                                "bike.location_name",
                            ],
                            "-",
                        )
                    ),
                    "message": self._safe_str(
                        self._pick(alert, ["message", "description", "reason"], "-")
                    ),
                    "recommendation": self._safe_str(
                        self._pick(alert, ["recommendation", "suggested_action"], "-")
                    ),
                }
            )

        return {
            "answer_type": "todays_ai_insights",
            "summary": self._build_summary_text(
                total_alerts=total_alerts,
                critical_count=critical_count,
                high_count=high_count,
                department_rankings=department_rankings,
                top_alert_types=top_alert_types,
            ),
            "metrics": {
                "total_alerts": total_alerts,
                "critical_alerts": critical_count,
                "high_alerts": high_count,
                "medium_alerts": medium_count,
                "low_alerts": low_count,
                "departments": len(department_rankings),
                "sampled_alert_items": len(alerts),
            },
            "top_risk_department": department_rankings[0] if department_rankings else None,
            "department_rankings": department_rankings[:safe_limit],
            "top_alert_type": top_alert_types[0] if top_alert_types else None,
            "top_alert_types": top_alert_types[:safe_limit],
            "critical_alerts": top_critical_alerts,
            "high_alert_sample_count": len(high_alerts),
            "recommended_actions": self._build_recommended_actions(
                department_rankings=department_rankings,
                top_alert_types=top_alert_types,
                critical_alerts=top_critical_alerts,
            ),
            "data_limitations": [
                "Demand forecast requires booking history and availability snapshots.",
                "Revenue analysis requires booking/payment data.",
                "Customer complaint analysis requires feedback/ticket data.",
                "Current insights are based on fleet status and operational alerts only.",
            ],
            "generated_at": self._now_utc(),
        }
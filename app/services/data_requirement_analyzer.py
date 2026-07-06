from datetime import datetime, timezone
from typing import Any, Dict, Optional


class DataRequirementAnalyzer:
    """
    Builds clear data-requirement responses for advanced admin tasks.

    This works with:
    - Keyword fallback
    - Groq capability router output
    """

    def __init__(self):
        self.task_rules = {
            "demand_forecast": {
                "display_name": "Demand Forecasting",
                "keywords": [
                    "demand trend",
                    "demand forecast",
                    "forecast demand",
                    "expected demand",
                    "predict demand",
                    "prediction",
                    "forecast",
                    "required stock",
                    "required vehicles",
                    "should be available",
                    "high demand",
                    "low demand",
                    "booking trend",
                    "rental trend",
                    "tomorrow demand",
                    "weekend demand",
                ],
                "required_data": [
                    {
                        "name": "Booking history",
                        "source_key": "booking_history",
                        "description": "Historical bookings/rentals for the required date range.",
                        "minimum_fields": [
                            "booking_id",
                            "vehicle_model",
                            "location_name",
                            "booking_created_at",
                            "rental_start_datetime",
                            "rental_end_datetime",
                            "booking_status",
                            "cancelled_at",
                            "customer_id or anonymized_customer_id",
                        ],
                    },
                    {
                        "name": "Availability snapshots",
                        "source_key": "availability_snapshots",
                        "description": "Vehicle availability by time, model, and location.",
                        "minimum_fields": [
                            "snapshot_datetime",
                            "location_name",
                            "vehicle_model",
                            "available_count",
                            "blocked_count",
                            "service_count",
                            "total_count",
                        ],
                    },
                    {
                        "name": "Current fleet status",
                        "source_key": "current_fleet",
                        "description": "Current vehicles, statuses, blocked vehicles, and service alerts.",
                        "minimum_fields": [
                            "vehicle_id",
                            "vehicle_model",
                            "location_name",
                            "status",
                            "service_alert",
                            "force_block_status",
                            "compliance_status",
                        ],
                    },
                ],
                "can_answer_now": [
                    "Current active locations",
                    "Current vehicles by location",
                    "Current model count",
                    "Blocked vehicles",
                    "Service alerts",
                    "Compliance alerts",
                    "Department-wise alert summary",
                ],
                "cannot_answer_yet": [
                    "True demand trend",
                    "Tomorrow demand prediction",
                    "Required stock recommendation",
                    "Model-wise demand forecast",
                    "Expected booking volume",
                ],
                "suggested_next_steps": [
                    "Connect a booking-history API endpoint.",
                    "Connect an availability-snapshot API endpoint.",
                    "Provide at least 4 to 8 weeks of booking history.",
                    "Then ask: forecast tomorrow demand for Koramangala by vehicle model.",
                ],
            },
            "shortage_prediction": {
                "display_name": "Shortage Prediction",
                "keywords": [
                    "shortage",
                    "vehicle shortage",
                    "stockout",
                    "not enough vehicles",
                    "low stock",
                    "insufficient stock",
                    "may face shortage",
                ],
                "required_data": [
                    {
                        "name": "Booking history",
                        "source_key": "booking_history",
                        "description": "Historical bookings by location and vehicle model.",
                        "minimum_fields": [
                            "booking_id",
                            "vehicle_model",
                            "location_name",
                            "rental_start_datetime",
                            "rental_end_datetime",
                            "booking_status",
                        ],
                    },
                    {
                        "name": "Availability snapshots",
                        "source_key": "availability_snapshots",
                        "description": "Available and unavailable vehicle counts over time.",
                        "minimum_fields": [
                            "snapshot_datetime",
                            "location_name",
                            "vehicle_model",
                            "available_count",
                            "blocked_count",
                            "service_count",
                            "total_count",
                        ],
                    },
                    {
                        "name": "Current fleet status",
                        "source_key": "current_fleet",
                        "description": "Current vehicle distribution and blocked/service status.",
                        "minimum_fields": [
                            "vehicle_id",
                            "vehicle_model",
                            "location_name",
                            "status",
                        ],
                    },
                ],
                "can_answer_now": [
                    "Current vehicle count by location",
                    "Current blocked vehicles",
                    "Current service alerts",
                ],
                "cannot_answer_yet": [
                    "Tomorrow shortage prediction",
                    "Expected stockout risk",
                    "Future location-wise shortage",
                ],
                "suggested_next_steps": [
                    "Connect booking history and availability snapshots.",
                    "Then ask: which locations may face shortage tomorrow?",
                ],
            },
            "fleet_reallocation": {
                "display_name": "Fleet Reallocation",
                "keywords": [
                    "reallocate",
                    "reallocation",
                    "fleet allocation",
                    "allocate vehicles",
                    "shift vehicles",
                    "move vehicles",
                    "transfer vehicles",
                    "overstocked",
                    "understocked",
                    "excess vehicles",
                ],
                "required_data": [
                    {
                        "name": "Booking history",
                        "source_key": "booking_history",
                        "description": "Demand pattern by model, date, and location.",
                        "minimum_fields": [
                            "booking_id",
                            "vehicle_model",
                            "location_name",
                            "rental_start_datetime",
                            "booking_status",
                        ],
                    },
                    {
                        "name": "Availability snapshots",
                        "source_key": "availability_snapshots",
                        "description": "Availability and idle stock trends across locations.",
                        "minimum_fields": [
                            "snapshot_datetime",
                            "location_name",
                            "vehicle_model",
                            "available_count",
                            "total_count",
                        ],
                    },
                    {
                        "name": "Current fleet status",
                        "source_key": "current_fleet",
                        "description": "Current available, blocked, and service vehicles.",
                        "minimum_fields": [
                            "vehicle_id",
                            "vehicle_model",
                            "location_name",
                            "status",
                        ],
                    },
                ],
                "can_answer_now": [
                    "Current fleet distribution",
                    "Current vehicle count by location",
                    "Current blocked/service vehicles",
                ],
                "cannot_answer_yet": [
                    "Optimal vehicle movement",
                    "Future reallocation recommendation",
                    "Overstock/understock prediction",
                ],
                "suggested_next_steps": [
                    "Connect booking history and availability snapshots.",
                    "Then ask: suggest fleet reallocation for tomorrow morning.",
                ],
            },
            "revenue_analysis": {
                "display_name": "Revenue Analysis",
                "keywords": [
                    "revenue",
                    "profit",
                    "earning",
                    "income",
                    "payment",
                    "highest revenue",
                    "lowest revenue",
                    "sales",
                    "pricing",
                    "financial performance",
                ],
                "required_data": [
                    {
                        "name": "Booking revenue data",
                        "source_key": "revenue_data",
                        "description": "Revenue and payment information for completed bookings.",
                        "minimum_fields": [
                            "booking_id",
                            "vehicle_model",
                            "location_name",
                            "booking_status",
                            "amount_paid",
                            "discount_amount",
                            "refund_amount",
                            "payment_status",
                            "booking_date",
                        ],
                    },
                ],
                "can_answer_now": [
                    "Fleet count",
                    "Alert count",
                    "Operational status",
                ],
                "cannot_answer_yet": [
                    "Revenue",
                    "Profit",
                    "Model-wise earnings",
                    "Location-wise earnings",
                    "Revenue trend",
                ],
                "suggested_next_steps": [
                    "Connect booking/payment API.",
                    "Provide revenue fields per booking.",
                    "Then ask: which location generated highest revenue last week?",
                ],
            },
            "customer_analysis": {
                "display_name": "Customer Analysis",
                "keywords": [
                    "customer complaint",
                    "complaint",
                    "customer feedback",
                    "feedback",
                    "rating",
                    "nps",
                    "customer satisfaction",
                    "repeat customer",
                    "churn",
                    "complaint trend",
                    "unhappy",
                ],
                "required_data": [
                    {
                        "name": "Customer support/feedback data",
                        "source_key": "customer_feedback",
                        "description": "Customer complaint, rating, and support-ticket data.",
                        "minimum_fields": [
                            "customer_id or anonymized_customer_id",
                            "booking_id",
                            "rating",
                            "complaint_category",
                            "feedback_text",
                            "ticket_status",
                            "created_at",
                        ],
                    },
                ],
                "can_answer_now": [
                    "Operational fleet status",
                    "Service alerts",
                    "Compliance alerts",
                ],
                "cannot_answer_yet": [
                    "Customer satisfaction analysis",
                    "Complaint trend",
                    "Churn prediction",
                    "Repeated complaint patterns",
                ],
                "suggested_next_steps": [
                    "Connect customer feedback/ticket API.",
                    "Upload complaint history CSV.",
                    "Then ask: which location has the highest customer complaints?",
                ],
            },
        }

    def _now_utc(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _normalize_query(self, user_query: str) -> str:
        return user_query.lower().strip()

    def _find_matching_task(self, user_query: str) -> Optional[Dict[str, Any]]:
        query = self._normalize_query(user_query)

        for task_type, rule in self.task_rules.items():
            for keyword in rule["keywords"]:
                if keyword in query:
                    matched_rule = dict(rule)
                    matched_rule["task_type"] = task_type
                    return matched_rule

        return None

    def _format_list_for_summary(self, items: list[str], limit: int = 4) -> str:
        if not items:
            return "none"

        visible = items[:limit]
        text = ", ".join(visible)

        if len(items) > limit:
            text += f", and {len(items) - limit} more"

        return text

    def _build_summary(
        self,
        rule: Dict[str, Any],
        capability: Optional[Dict[str, Any]] = None,
    ) -> str:
        display_name = rule["display_name"]

        capability = capability or {}

        location = capability.get("location")
        vehicle_model = capability.get("vehicle_model")
        time_window = capability.get("time_window")

        missing_sources = capability.get("missing_data_sources") or []
        required_sources = capability.get("required_data_sources") or []

        context_parts = []

        if vehicle_model:
            context_parts.append(f"vehicle model: {vehicle_model}")

        if location:
            context_parts.append(f"location: {location}")

        if time_window:
            context_parts.append(f"time window: {time_window}")

        context_text = ""

        if context_parts:
            context_text = " I understood the context as " + ", ".join(context_parts) + "."

        missing_text = ""

        if missing_sources:
            missing_text = (
                " Missing data sources: "
                + self._format_list_for_summary(missing_sources)
                + "."
            )
        elif required_sources:
            missing_text = (
                " Required data sources: "
                + self._format_list_for_summary(required_sources)
                + "."
            )

        can_now = self._format_list_for_summary(rule["can_answer_now"], limit=3)
        cannot_yet = self._format_list_for_summary(rule["cannot_answer_yet"], limit=3)

        return (
            f"This looks like a {display_name} request."
            f"{context_text} "
            "I should not answer this using only current fleet data because it would be a guess. "
            f"{missing_text} "
            f"With the current system, I can answer: {can_now}. "
            f"I cannot accurately answer yet: {cannot_yet}."
        )

    def analyze_capability(
        self,
        user_query: str,
        request_id: str,
        capability: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        task_type = capability.get("task_type")

        if task_type not in self.task_rules:
            return None

        rule = dict(self.task_rules[task_type])
        rule["task_type"] = task_type

        return self._build_response(
            rule=rule,
            request_id=request_id,
            capability=capability,
        )

    def analyze(
        self,
        user_query: str,
        request_id: str,
    ) -> Optional[Dict[str, Any]]:
        matched_rule = self._find_matching_task(user_query)

        if not matched_rule:
            return None

        return self._build_response(
            rule=matched_rule,
            request_id=request_id,
            capability=None,
        )

    def _build_response(
        self,
        rule: Dict[str, Any],
        request_id: str,
        capability: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        capability = capability or {}

        return {
            "answer_type": "data_requirement",
            "task_type": rule["task_type"],
            "summary": self._build_summary(rule, capability),
            "capability": capability,
            "can_answer_now": rule["can_answer_now"],
            "cannot_answer_yet": rule["cannot_answer_yet"],
            "required_data": rule["required_data"],
            "required_data_sources": capability.get("required_data_sources", []),
            "available_data_sources": capability.get("available_data_sources", []),
            "missing_data_sources": capability.get("missing_data_sources", []),
            "suggested_next_steps": rule["suggested_next_steps"],
            "recommended_user_reply": self._build_recommended_reply(rule),
            "example_supported_queries_now": [
                "Tell me all the active locations",
                "total Activa at Koramangala today",
                "show service alerts",
                "show dashboard summary",
                "show department-wise alerts",
            ],
            "request_id": request_id,
            "timestamp_utc": self._now_utc(),
        }

    def _build_recommended_reply(self, rule: Dict[str, Any]) -> str:
        task_type = rule["task_type"]

        if task_type in [
            "demand_forecast",
            "shortage_prediction",
            "fleet_reallocation",
        ]:
            return (
                "Please provide booking history for the last 4 to 8 weeks and "
                "availability snapshots with vehicle model, location, booking date, "
                "rental start/end time, booking status, available count, blocked count, "
                "service count, and total fleet count."
            )

        if task_type == "revenue_analysis":
            return (
                "Please provide booking/payment data with amount paid, discount, "
                "refund, booking status, vehicle model, location, and booking date."
            )

        if task_type == "customer_analysis":
            return (
                "Please provide customer feedback, complaint, ticket, or rating data "
                "mapped to booking, location, and vehicle model where possible."
            )

        return (
            "Please provide the required historical/business data so I can answer this accurately."
        )
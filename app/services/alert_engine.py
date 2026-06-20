from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


class AlertEngine:
    """
    AlertEngine checks raw bike data from Sir's optimized API
    and creates department-wise operational alerts.

    This version:
    - generates alert summaries
    - avoids dumping thousands of alerts by default
    - supports filtering by department
    - supports filtering by severity
    - supports limited alert details
    - skips inactive Sold/Missing records by default
    - provides full filtered alert items for SQLite storage
    """

    def __init__(self):
        self.service_km_warning_threshold = 500

        self.severity_priority = {
            "critical": 1,
            "high": 2,
            "medium": 3,
            "low": 4
        }

    def _safe_int(self, value: Any) -> Optional[int]:
        """
        Safely converts values like '125001' into int.
        Returns None if value is missing or invalid.
        """

        try:
            if value is None or value == "":
                return None

            return int(float(str(value).strip()))

        except Exception:
            return None

    def _safe_str(self, value: Any) -> str:
        """
        Safely converts any value into a clean string.
        """

        if value is None:
            return ""

        return str(value).strip()

    def _parse_date(self, value: Any) -> Optional[datetime]:
        """
        Tries to parse date values from the API.

        Supported examples:
        - 2026-11-21
        - 23/08/2027
        - 2026/06/22 19
        """

        if not value:
            return None

        value = str(value).strip()

        possible_formats = [
            "%Y-%m-%d",
            "%d/%m/%Y",
            "%Y/%m/%d %H",
            "%Y/%m/%d",
            "%Y-%m-%d %H",
        ]

        for fmt in possible_formats:
            try:
                return datetime.strptime(value, fmt).replace(tzinfo=timezone.utc)
            except Exception:
                continue

        return None

    def _should_skip_bike(
        self,
        bike: Dict[str, Any],
        include_inactive: bool
    ) -> bool:
        """
        Skips inactive/non-operational records by default.

        Example inactive locations:
        - Sold 998
        - missing 999
        """

        if include_inactive:
            return False

        location = self._safe_str(bike.get("location_name")).lower()

        inactive_keywords = [
            "sold",
            "missing"
        ]

        return any(keyword in location for keyword in inactive_keywords)

    def _create_alert(
        self,
        department: str,
        severity: str,
        alert_type: str,
        message: str,
        bike: Dict[str, Any],
        recommendation: str
    ) -> Dict[str, Any]:
        """
        Creates one standard alert object.

        This standard structure is useful for:
        - API responses
        - SQLite storage
        - dashboards
        - email alerts
        """

        return {
            "department": department,
            "severity": severity,
            "alert_type": alert_type,
            "message": message,
            "recommendation": recommendation,
            "bike": {
                "reg_num": bike.get("reg_num"),
                "bike_type": bike.get("bike_type"),
                "location_name": bike.get("location_name"),
                "current_km": bike.get("Current_km"),
                "next_service_km": bike.get("nxt_service"),
                "force_block": bike.get("forceBlock"),
                "service_alert": bike.get("serviceAlert"),
                "booking_status": bike.get("booking_status"),
                "insurance": bike.get("Insurance"),
                "emission": bike.get("emission"),
            }
        }

    def _generate_all_alerts(
        self,
        api_data: List[Dict[str, Any]],
        include_inactive: bool = False
    ) -> Dict[str, Any]:
        """
        Generates all alerts internally.

        This may generate thousands of alerts.
        Public methods will summarize/filter/limit them.
        """

        alerts: List[Dict[str, Any]] = []
        skipped_records = 0

        for bike in api_data:
            if self._should_skip_bike(
                bike=bike,
                include_inactive=include_inactive
            ):
                skipped_records += 1
                continue

            reg_num = self._safe_str(bike.get("reg_num"))
            location = self._safe_str(bike.get("location_name"))

            service_alert = self._safe_str(
                bike.get("serviceAlert")
            ).lower()

            force_block = self._safe_str(
                bike.get("forceBlock")
            ).lower()

            booking_status = self._safe_str(
                bike.get("booking_status")
            ).lower()

            current_km = self._safe_int(bike.get("Current_km"))
            next_service_km = self._safe_int(bike.get("nxt_service"))

            # Rule 1: Service alert is ON
            if service_alert == "on":
                alerts.append(
                    self._create_alert(
                        department="Service Department",
                        severity="high",
                        alert_type="SERVICE_ALERT_ON",
                        message=f"{reg_num} has serviceAlert ON at {location}.",
                        bike=bike,
                        recommendation="Schedule service inspection or maintenance check."
                    )
                )

            # Rule 2: Force block is active
            if force_block and force_block != "off":
                department = "Operations Department"
                severity = "medium"
                recommendation = "Review force block reason and update vehicle status."

                if force_block == "recovery":
                    department = "Recovery Department"
                    severity = "high"
                    recommendation = "Check recovery status and coordinate vehicle retrieval."

                elif force_block == "spareblock":
                    department = "Fleet Department"
                    severity = "medium"
                    recommendation = "Verify why vehicle is marked as spare block."

                alerts.append(
                    self._create_alert(
                        department=department,
                        severity=severity,
                        alert_type="FORCE_BLOCK_ACTIVE",
                        message=f"{reg_num} is force blocked as '{force_block}' at {location}.",
                        bike=bike,
                        recommendation=recommendation
                    )
                )

            # Rule 3: Service KM check
            if current_km is not None and next_service_km is not None:
                km_left = next_service_km - current_km

                if km_left <= 0:
                    alerts.append(
                        self._create_alert(
                            department="Service Department",
                            severity="critical",
                            alert_type="SERVICE_OVERDUE_BY_KM",
                            message=(
                                f"{reg_num} has crossed next service KM. "
                                f"Current: {current_km}, "
                                f"Next Service: {next_service_km}."
                            ),
                            bike=bike,
                            recommendation="Immediately schedule service before further usage."
                        )
                    )

                elif km_left <= self.service_km_warning_threshold:
                    alerts.append(
                        self._create_alert(
                            department="Service Department",
                            severity="medium",
                            alert_type="SERVICE_DUE_SOON_BY_KM",
                            message=(
                                f"{reg_num} is close to service. "
                                f"Only {km_left} km left."
                            ),
                            bike=bike,
                            recommendation="Plan service soon to avoid downtime."
                        )
                    )

            # Rule 4: Booking recovered status
            if booking_status == "recovered":
                alerts.append(
                    self._create_alert(
                        department="Recovery Department",
                        severity="medium",
                        alert_type="BOOKING_RECOVERED",
                        message=f"{reg_num} has booking status marked as recovered.",
                        bike=bike,
                        recommendation="Verify vehicle condition and mark it operational if ready."
                    )
                )

            # Rule 5: Insurance expired
            insurance_date = self._parse_date(bike.get("Insurance"))

            if insurance_date:
                today = datetime.now(timezone.utc)

                if insurance_date < today:
                    alerts.append(
                        self._create_alert(
                            department="Compliance Department",
                            severity="critical",
                            alert_type="INSURANCE_EXPIRED",
                            message=(
                                f"{reg_num} insurance expired on "
                                f"{bike.get('Insurance')}."
                            ),
                            bike=bike,
                            recommendation="Renew insurance immediately and block vehicle if required."
                        )
                    )

            # Rule 6: Emission expired
            emission_date = self._parse_date(bike.get("emission"))

            if emission_date:
                today = datetime.now(timezone.utc)

                if emission_date < today:
                    alerts.append(
                        self._create_alert(
                            department="Compliance Department",
                            severity="critical",
                            alert_type="EMISSION_EXPIRED",
                            message=(
                                f"{reg_num} emission certificate expired on "
                                f"{bike.get('emission')}."
                            ),
                            bike=bike,
                            recommendation="Renew emission certificate immediately."
                        )
                    )

        return {
            "alerts": alerts,
            "skipped_records": skipped_records
        }

    def _filter_alerts(
        self,
        alerts: List[Dict[str, Any]],
        department: Optional[str] = None,
        severity: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Filters alerts by department and/or severity.
        """

        filtered_alerts = alerts

        if department:
            department_lower = department.strip().lower()

            filtered_alerts = [
                alert for alert in filtered_alerts
                if alert.get("department", "").lower() == department_lower
            ]

        if severity:
            severity_lower = severity.strip().lower()

            filtered_alerts = [
                alert for alert in filtered_alerts
                if alert.get("severity", "").lower() == severity_lower
            ]

        return filtered_alerts

    def _sort_alerts_by_priority(
        self,
        alerts: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Sorts alerts by severity priority:
        critical → high → medium → low
        """

        return sorted(
            alerts,
            key=lambda alert: self.severity_priority.get(
                alert.get("severity", "low"),
                99
            )
        )

    def _build_counts(
        self,
        alerts: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Builds severity, department, and alert type counts.
        """

        severity_count = {
            "critical": 0,
            "high": 0,
            "medium": 0,
            "low": 0
        }

        department_count: Dict[str, int] = {}
        alert_type_count: Dict[str, int] = {}

        for alert in alerts:
            severity = alert.get("severity", "low")
            department = alert.get("department", "Unknown Department")
            alert_type = alert.get("alert_type", "UNKNOWN_ALERT")

            if severity not in severity_count:
                severity_count[severity] = 0

            severity_count[severity] += 1
            department_count[department] = (
                department_count.get(department, 0) + 1
            )
            alert_type_count[alert_type] = (
                alert_type_count.get(alert_type, 0) + 1
            )

        return {
            "severity_count": severity_count,
            "department_count": department_count,
            "alert_type_count": alert_type_count
        }

    def generate_alerts(
        self,
        api_data: List[Dict[str, Any]],
        include_details: bool = False,
        max_alerts: int = 20,
        department: Optional[str] = None,
        severity: Optional[str] = None,
        include_inactive: bool = False
    ) -> Dict[str, Any]:
        """
        Public function used by FastAPI.

        Default:
        - summary only
        - no huge alert dump
        - inactive Sold/Missing records skipped

        Optional:
        - include_details=True gives limited alert details
        - max_alerts controls how many details are returned
        - department filters by department
        - severity filters by severity
        """

        generated_at = datetime.now(timezone.utc).isoformat()

        internal_result = self._generate_all_alerts(
            api_data=api_data,
            include_inactive=include_inactive
        )

        all_alerts = internal_result["alerts"]
        skipped_records = internal_result["skipped_records"]

        filtered_alerts = self._filter_alerts(
            alerts=all_alerts,
            department=department,
            severity=severity
        )

        sorted_alerts = self._sort_alerts_by_priority(filtered_alerts)

        safe_max_alerts = max(1, min(max_alerts, 100))

        counts = self._build_counts(filtered_alerts)

        response = {
            "generated_at_utc": generated_at,
            "filters": {
                "department": department,
                "severity": severity,
                "include_details": include_details,
                "max_alerts": safe_max_alerts,
                "include_inactive": include_inactive
            },
            "records": {
                "total_records_received": len(api_data),
                "total_records_checked": len(api_data) - skipped_records,
                "total_records_skipped": skipped_records
            },
            "alerts_summary": {
                "total_alerts_before_filters": len(all_alerts),
                "total_alerts_after_filters": len(filtered_alerts),
                "severity_count": counts["severity_count"],
                "department_count": counts["department_count"],
                "alert_type_count": counts["alert_type_count"]
            }
        }

        if include_details:
            response["alerts"] = sorted_alerts[:safe_max_alerts]
            response["returned_alert_count"] = len(response["alerts"])
            response["note"] = (
                f"Showing top {len(response['alerts'])} alerts only. "
                f"Use max_alerts to change the limit."
            )

        else:
            response["alerts"] = []
            response["returned_alert_count"] = 0
            response["note"] = (
                "Summary only. Use include_details=true to view limited alert details."
            )

        return response

    def generate_alert_items_for_storage(
        self,
        api_data: List[Dict[str, Any]],
        department: Optional[str] = None,
        severity: Optional[str] = None,
        include_inactive: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Generates all filtered alert items for database storage.

        This is separate from generate_alerts() because:
        - generate_alerts() returns summary-first output
        - storage needs full filtered alert items
        """

        internal_result = self._generate_all_alerts(
            api_data=api_data,
            include_inactive=include_inactive
        )

        all_alerts = internal_result["alerts"]

        filtered_alerts = self._filter_alerts(
            alerts=all_alerts,
            department=department,
            severity=severity
        )

        return self._sort_alerts_by_priority(filtered_alerts)
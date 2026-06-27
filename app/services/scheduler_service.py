import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.services.alert_engine import AlertEngine
from app.storage.alert_repository import AlertRepository
from app.tools.optimized_api import call_sir_optimized_api_with_metadata


class SchedulerService:
    """
    SchedulerService runs alert checks automatically at fixed intervals.

    MVP responsibility:
    - Call optimized API
    - Generate alerts
    - Save alert run in SQLite
    - Prevent duplicate/frequent alert runs using cooldown
    - Track scheduler status
    """

    def __init__(
        self,
        alert_engine: Optional[AlertEngine] = None,
        alert_repo: Optional[AlertRepository] = None
    ):
        self.alert_engine = alert_engine or AlertEngine()
        self.alert_repo = alert_repo or AlertRepository()

        self.scheduler = AsyncIOScheduler(timezone="UTC")
        self.job_id = "scheduled_alert_check"

        self.enabled = self._get_bool_env(
            "ALERT_SCHEDULER_ENABLED",
            default=False
        )

        self.run_on_startup = self._get_bool_env(
            "ALERT_SCHEDULER_RUN_ON_STARTUP",
            default=False
        )

        self.interval_minutes = self._get_int_env(
            "ALERT_SCHEDULER_INTERVAL_MINUTES",
            default=60
        )

        self.cooldown_minutes = self._get_int_env(
            "ALERT_RUN_COOLDOWN_MINUTES",
            default=30
        )

        self.is_job_running = False

        self.last_run_started_at: Optional[str] = None
        self.last_run_finished_at: Optional[str] = None
        self.last_success_at: Optional[str] = None
        self.last_error_at: Optional[str] = None
        self.last_error_message: Optional[str] = None
        self.last_run_id: Optional[str] = None
        self.last_skip_reason: Optional[str] = None

    def _get_bool_env(self, key: str, default: bool = False) -> bool:
        value = os.getenv(key)

        if value is None:
            return default

        return value.strip().lower() in ["true", "1", "yes", "on"]

    def _get_int_env(self, key: str, default: int) -> int:
        value = os.getenv(key)

        if value is None:
            return default

        try:
            parsed_value = int(value)
            return max(0, parsed_value)
        except Exception:
            return default

    def start(self) -> Dict[str, Any]:
        """
        Starts scheduler only if ALERT_SCHEDULER_ENABLED=true.
        """

        if not self.enabled:
            return {
                "status": "disabled",
                "message": "Scheduler is disabled. Set ALERT_SCHEDULER_ENABLED=true to enable it.",
                "interval_minutes": self.interval_minutes,
                "cooldown_minutes": self.cooldown_minutes
            }

        if self.scheduler.running:
            return {
                "status": "already_running",
                "message": "Scheduler is already running.",
                "interval_minutes": self.interval_minutes,
                "cooldown_minutes": self.cooldown_minutes
            }

        next_run_time = None

        if self.run_on_startup:
            next_run_time = datetime.now(timezone.utc)

        self.scheduler.add_job(
            self.run_alert_check_now,
            trigger=IntervalTrigger(minutes=self.interval_minutes),
            id=self.job_id,
            replace_existing=True,
            kwargs={
                "triggered_by": "scheduled",
                "force": False
            },
            next_run_time=next_run_time
        )

        self.scheduler.start()

        return {
            "status": "running",
            "message": "Scheduler started successfully.",
            "interval_minutes": self.interval_minutes,
            "cooldown_minutes": self.cooldown_minutes,
            "run_on_startup": self.run_on_startup
        }

    def shutdown(self) -> Dict[str, Any]:
        """
        Stops scheduler when FastAPI shuts down.
        """

        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)

            return {
                "status": "stopped",
                "message": "Scheduler stopped successfully."
            }

        return {
            "status": "not_running",
            "message": "Scheduler was not running."
        }

    async def run_alert_check_now(
        self,
        triggered_by: str = "manual",
        force: bool = False
    ) -> Dict[str, Any]:
        """
        Runs alert check immediately.

        Cooldown behavior:
        - If a recent alert run exists, skip.
        - Use force=true to bypass cooldown.
        """

        if self.is_job_running:
            return {
                "status": "skipped",
                "message": "An alert check is already running.",
                "triggered_by": triggered_by
            }

        self.is_job_running = True
        self.last_run_started_at = datetime.now(timezone.utc).isoformat()
        self.last_skip_reason = None

        try:
            cooldown_check = self.alert_repo.check_recent_alert_run(
                cooldown_minutes=self.cooldown_minutes
            )

            if cooldown_check.get("should_skip") and not force:
                self.last_skip_reason = cooldown_check.get("reason")
                self.last_run_id = cooldown_check.get("latest_run_id")

                return {
                    "status": "skipped",
                    "message": "Recent alert run already exists. Skipping to prevent duplicate/frequent runs.",
                    "triggered_by": triggered_by,
                    "force": force,
                    "cooldown": cooldown_check
                }

            api_result = await call_sir_optimized_api_with_metadata()

            if not api_result.get("success"):
                error_message = api_result.get("error") or "API call failed"

                self.last_error_at = datetime.now(timezone.utc).isoformat()
                self.last_error_message = error_message

                return {
                    "status": "error",
                    "message": "Could not fetch data from optimized API.",
                    "triggered_by": triggered_by,
                    "error": error_message,
                    "api_status_code": api_result.get("status_code")
                }

            api_data = api_result.get("data", [])

            if not isinstance(api_data, list):
                error_message = f"Unexpected API data format: {type(api_data)}"

                self.last_error_at = datetime.now(timezone.utc).isoformat()
                self.last_error_message = error_message

                return {
                    "status": "error",
                    "message": "API returned unexpected data format.",
                    "triggered_by": triggered_by,
                    "error": error_message
                }

            alert_result = self.alert_engine.generate_alerts(
                api_data=api_data,
                include_details=False,
                max_alerts=20,
                department=None,
                severity=None,
                include_inactive=False
            )

            alerts_to_save = self.alert_engine.generate_alert_items_for_storage(
                api_data=api_data,
                department=None,
                severity=None,
                include_inactive=False
            )

            run_id = self.alert_repo.save_alert_run_with_items(
                alert_result=alert_result,
                alerts_to_save=alerts_to_save
            )

            self.last_run_id = run_id
            self.last_success_at = datetime.now(timezone.utc).isoformat()
            self.last_error_message = None
            self.last_skip_reason = None

            return {
                "status": "success",
                "message": "Scheduled alert check completed and saved successfully.",
                "triggered_by": triggered_by,
                "force": force,
                "run_id": run_id,
                "total_records_checked": alert_result.get("records", {}).get("total_records_checked"),
                "saved_alert_count": len(alerts_to_save),
                "severity_count": alert_result.get("alerts_summary", {}).get("severity_count"),
                "department_count": alert_result.get("alerts_summary", {}).get("department_count")
            }

        except Exception as e:
            error_message = f"{type(e).__name__}: {str(e)}"

            self.last_error_at = datetime.now(timezone.utc).isoformat()
            self.last_error_message = error_message

            return {
                "status": "error",
                "message": "Scheduled alert check failed.",
                "triggered_by": triggered_by,
                "error": error_message
            }

        finally:
            self.last_run_finished_at = datetime.now(timezone.utc).isoformat()
            self.is_job_running = False

    def get_status(self) -> Dict[str, Any]:
        """
        Returns scheduler status.
        """

        job = self.scheduler.get_job(self.job_id)

        next_run_time = None

        if job and job.next_run_time:
            next_run_time = job.next_run_time.isoformat()

        cooldown_check = self.alert_repo.check_recent_alert_run(
            cooldown_minutes=self.cooldown_minutes
        )

        return {
            "enabled": self.enabled,
            "scheduler_running": self.scheduler.running,
            "job_id": self.job_id,
            "interval_minutes": self.interval_minutes,
            "cooldown_minutes": self.cooldown_minutes,
            "run_on_startup": self.run_on_startup,
            "is_job_running": self.is_job_running,
            "next_run_time_utc": next_run_time,
            "last_run_started_at": self.last_run_started_at,
            "last_run_finished_at": self.last_run_finished_at,
            "last_success_at": self.last_success_at,
            "last_error_at": self.last_error_at,
            "last_error_message": self.last_error_message,
            "last_skip_reason": self.last_skip_reason,
            "last_run_id": self.last_run_id,
            "cooldown": cooldown_check
        }
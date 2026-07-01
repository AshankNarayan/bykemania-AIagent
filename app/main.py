import os
from typing import Optional

from dotenv import load_dotenv

load_dotenv()

from fastapi import Depends, FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

from app.agent import BykeManiaAgent
from app.storage.log_repository import AgentLogRepository
from app.storage.alert_repository import AlertRepository
from app.tools.optimized_api import call_sir_optimized_api_with_metadata
from app.services.alert_engine import AlertEngine
from app.services.scheduler_service import SchedulerService
from app.security.api_key import verify_api_key


APP_VERSION = "0.1.1"


app = FastAPI(
    title="BykeMania AI Agent",
    description="Natural Language AI Agent for BykeMania Operations",
    version=APP_VERSION,

    # Important for Render / Swagger deployment
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Shared service instances
agent = BykeManiaAgent()
log_repo = AgentLogRepository()
alert_engine = AlertEngine()
alert_repo = AlertRepository()
scheduler_service = SchedulerService(
    alert_engine=alert_engine,
    alert_repo=alert_repo
)


class ChatRequest(BaseModel):
    query: str


def get_alert_run_cooldown_minutes() -> int:
    """
    Reads cooldown value from environment variables.

    If ALERT_RUN_COOLDOWN_MINUTES=30,
    then the system avoids saving another alert run within 30 minutes
    unless force=true.
    """

    try:
        return max(0, int(os.getenv("ALERT_RUN_COOLDOWN_MINUTES", "30")))
    except Exception:
        return 30


@app.on_event("startup")
async def startup_event():
    """
    Starts scheduler when FastAPI starts, only if enabled in environment variables.
    """

    scheduler_status = scheduler_service.start()
    print("[Scheduler Startup]", scheduler_status)


@app.on_event("shutdown")
async def shutdown_event():
    """
    Stops scheduler when FastAPI shuts down.
    """

    scheduler_status = scheduler_service.shutdown()
    print("[Scheduler Shutdown]", scheduler_status)


@app.head("/")
async def root_head():
    """
    Lightweight HEAD endpoint for platform health checks.

    This prevents Render from showing:
    HEAD / 405 Method Not Allowed
    """

    return Response(status_code=200)


@app.get("/")
async def root():
    """
    Public health endpoint.

    This endpoint is intentionally not API-key protected.
    """

    return {
        "message": "BykeMania AI Agent is running 🚀",
        "status": "healthy",
        "version": APP_VERSION,
        "docs": "/docs",
        "openapi_schema": "/openapi.json",
        "security": {
            "protected_endpoints_require": "x-api-key header"
        },
        "available_endpoints": {
            "chat": "POST /chat",
            "recent_logs": "GET /logs/recent",
            "full_log": "GET /logs/{request_id}",

            "alert_run": "GET /alerts/run",
            "alert_run_force": "GET /alerts/run?force=true",
            "alert_history": "GET /alerts/history",
            "latest_alert_run": "GET /alerts/latest",
            "alert_run_details": "GET /alerts/history/{run_id}",

            "dashboard_summary": "GET /dashboard/summary",
            "dashboard_departments": "GET /dashboard/departments",
            "dashboard_department_detail": "GET /dashboard/department/{department_name}",

            "scheduler_status": "GET /scheduler/status",
            "scheduler_run_now": "POST /scheduler/run-now",
            "scheduler_run_now_force": "POST /scheduler/run-now?force=true"
        }
    }


@app.post(
    "/chat",
    dependencies=[Depends(verify_api_key)]
)
async def chat(request: ChatRequest):
    """
    Main chat endpoint.

    Protected by x-api-key.

    Flow:
    1. User sends natural language query
    2. Agent parses query
    3. Agent calls optimized backend API when needed
    4. Agent formats response
    5. Query + API response + final response are logged
    """

    response_data = await agent.process_query(request.query)

    return {
        "query": request.query,
        "response": response_data,
        "status": "success"
    }


@app.get(
    "/alerts/run",
    dependencies=[Depends(verify_api_key)]
)
async def run_alert_check(
    include_details: bool = False,
    max_alerts: int = 20,
    department: Optional[str] = None,
    severity: Optional[str] = None,
    include_inactive: bool = False,
    force: bool = False
):
    """
    Runs alert checking on current fleet data and saves the alert run.

    Protected by x-api-key.

    Cooldown protection:
    - prevents duplicate/frequent alert runs
    - use force=true to bypass cooldown

    Examples:
    /alerts/run
    /alerts/run?force=true
    /alerts/run?include_details=true&max_alerts=20
    """

    cooldown_minutes = get_alert_run_cooldown_minutes()

    cooldown_check = alert_repo.check_recent_alert_run(
        cooldown_minutes=cooldown_minutes
    )

    if cooldown_check.get("should_skip") and not force:
        return {
            "status": "skipped",
            "message": "Recent alert run already exists. Skipping to prevent duplicate/frequent runs.",
            "force": force,
            "cooldown": cooldown_check
        }

    api_result = await call_sir_optimized_api_with_metadata()

    if not api_result.get("success"):
        return {
            "status": "error",
            "message": "Could not fetch data from optimized API.",
            "error": api_result.get("error"),
            "api_status_code": api_result.get("status_code")
        }

    api_data = api_result.get("data", [])

    if not isinstance(api_data, list):
        return {
            "status": "error",
            "message": "API returned unexpected data format.",
            "data_type": str(type(api_data))
        }

    alert_result = alert_engine.generate_alerts(
        api_data=api_data,
        include_details=include_details,
        max_alerts=max_alerts,
        department=department,
        severity=severity,
        include_inactive=include_inactive
    )

    alerts_to_save = alert_engine.generate_alert_items_for_storage(
        api_data=api_data,
        department=department,
        severity=severity,
        include_inactive=include_inactive
    )

    run_id = alert_repo.save_alert_run_with_items(
        alert_result=alert_result,
        alerts_to_save=alerts_to_save
    )

    alert_result["run_id"] = run_id
    alert_result["saved_alert_count"] = len(alerts_to_save)

    return {
        "status": "success",
        "message": "Alert check completed and saved successfully.",
        "force": force,
        "run_id": run_id,
        "result": alert_result
    }


@app.get(
    "/alerts/history",
    dependencies=[Depends(verify_api_key)]
)
async def get_alert_history(limit: int = 10):
    """
    Returns recent alert scan history.

    Protected by x-api-key.
    """

    safe_limit = max(1, min(limit, 100))

    history = alert_repo.get_recent_alert_runs(limit=safe_limit)

    return {
        "status": "success",
        "total": len(history),
        "history": history
    }


@app.get(
    "/alerts/latest",
    dependencies=[Depends(verify_api_key)]
)
async def get_latest_alert_run(
    limit: int = 100,
    department: Optional[str] = None,
    severity: Optional[str] = None
):
    """
    Returns the latest saved alert run with limited alert items.

    Protected by x-api-key.
    """

    latest = alert_repo.get_latest_alert_run(
        limit=limit,
        department=department,
        severity=severity
    )

    if not latest:
        raise HTTPException(
            status_code=404,
            detail="No alert history found"
        )

    return {
        "status": "success",
        "latest_alert_run": latest
    }


@app.get(
    "/alerts/history/{run_id}",
    dependencies=[Depends(verify_api_key)]
)
async def get_alert_run_details(
    run_id: str,
    limit: int = 100,
    department: Optional[str] = None,
    severity: Optional[str] = None
):
    """
    Returns one saved alert run with limited alert items.

    Protected by x-api-key.
    """

    alert_run = alert_repo.get_alert_run_by_id(
        run_id=run_id,
        limit=limit,
        department=department,
        severity=severity
    )

    if not alert_run:
        raise HTTPException(
            status_code=404,
            detail="Alert run not found"
        )

    return {
        "status": "success",
        "alert_run": alert_run
    }


@app.get(
    "/dashboard/summary",
    dependencies=[Depends(verify_api_key)]
)
async def dashboard_summary():
    """
    Dashboard home summary.

    Protected by x-api-key.
    """

    summary = alert_repo.get_dashboard_summary()

    if not summary:
        raise HTTPException(
            status_code=404,
            detail="No alert history found. Run /alerts/run first."
        )

    return {
        "status": "success",
        "dashboard": summary
    }


@app.get(
    "/dashboard/departments",
    dependencies=[Depends(verify_api_key)]
)
async def dashboard_departments(run_id: Optional[str] = None):
    """
    Returns department-wise alert cards.

    Protected by x-api-key.
    """

    cards = alert_repo.get_department_cards(run_id=run_id)

    return {
        "status": "success",
        "total_departments": len(cards),
        "departments": cards
    }


@app.get(
    "/dashboard/department/{department_name}",
    dependencies=[Depends(verify_api_key)]
)
async def dashboard_department_detail(
    department_name: str,
    run_id: Optional[str] = None,
    limit: int = 50,
    severity: Optional[str] = None
):
    """
    Returns department-specific dashboard data.

    Protected by x-api-key.
    """

    data = alert_repo.get_department_dashboard(
        department_name=department_name,
        run_id=run_id,
        limit=limit,
        severity=severity
    )

    if not data:
        raise HTTPException(
            status_code=404,
            detail="No alert history found. Run /alerts/run first."
        )

    return {
        "status": "success",
        "dashboard": data
    }


@app.get(
    "/scheduler/status",
    dependencies=[Depends(verify_api_key)]
)
async def scheduler_status():
    """
    Returns scheduler status.

    Protected by x-api-key.
    """

    return {
        "status": "success",
        "scheduler": scheduler_service.get_status()
    }


@app.post(
    "/scheduler/run-now",
    dependencies=[Depends(verify_api_key)]
)
async def scheduler_run_now(force: bool = False):
    """
    Manually triggers the same alert check used by the scheduler.

    Protected by x-api-key.

    Cooldown protection:
    - by default it skips if a recent run already exists
    - use force=true to bypass cooldown
    """

    result = await scheduler_service.run_alert_check_now(
        triggered_by="manual_endpoint",
        force=force
    )

    return result


@app.get(
    "/logs/recent",
    dependencies=[Depends(verify_api_key)]
)
async def get_recent_logs(limit: int = 10):
    """
    Returns recent query logs.

    Protected by x-api-key.
    """

    safe_limit = max(1, min(limit, 50))

    logs = log_repo.get_recent_logs(limit=safe_limit)

    return {
        "total": len(logs),
        "logs": logs
    }


@app.get(
    "/logs/{request_id}",
    dependencies=[Depends(verify_api_key)]
)
async def get_log_by_request_id(request_id: str):
    """
    Returns full details of one logged query.

    Protected by x-api-key.
    """

    log = log_repo.get_log_by_request_id(request_id)

    if not log:
        raise HTTPException(
            status_code=404,
            detail="Log not found"
        )

    return log


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        port=8000,
        reload=True
    )
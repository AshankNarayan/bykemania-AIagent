from typing import Optional

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

from app.agent import BykeManiaAgent
from app.storage.log_repository import AgentLogRepository
from app.storage.alert_repository import AlertRepository
from app.tools.optimized_api import call_sir_optimized_api_with_metadata
from app.services.alert_engine import AlertEngine


app = FastAPI(
    title="BykeMania AI Agent",
    description="Natural Language AI Agent for BykeMania Operations",
    version="0.1.0"
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


class ChatRequest(BaseModel):
    query: str


@app.get("/")
async def root():
    return {
        "message": "BykeMania AI Agent is running 🚀",
        "status": "healthy",
        "version": "0.1.0",
        "available_endpoints": {
            "chat": "POST /chat",
            "recent_logs": "GET /logs/recent",
            "full_log": "GET /logs/{request_id}",

            "alert_run": "GET /alerts/run",
            "alert_history": "GET /alerts/history",
            "latest_alert_run": "GET /alerts/latest",
            "alert_run_details": "GET /alerts/history/{run_id}"
        }
    }


@app.post("/chat")
async def chat(request: ChatRequest):
    """
    Main chat endpoint.

    Flow:
    1. User sends natural language query
    2. Agent parses query
    3. Agent calls optimized PHP API
    4. Agent formats response
    5. Query + API response + final response are logged
    """

    response_data = await agent.process_query(request.query)

    return {
        "query": request.query,
        "response": response_data,
        "status": "success"
    }


@app.get("/alerts/run")
async def run_alert_check(
    include_details: bool = False,
    max_alerts: int = 20,
    department: Optional[str] = None,
    severity: Optional[str] = None,
    include_inactive: bool = False
):
    """
    Runs alert checking on current fleet data and saves the alert run.

    Default behavior:
    - returns summary only
    - avoids huge output
    - skips inactive Sold/Missing records
    - saves full filtered alert items in SQLite

    Optional query parameters:
    - include_details=true
    - max_alerts=20
    - department=Fleet Department
    - severity=critical
    - include_inactive=true
    """

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

    # Summary-first response for API/dashboard
    alert_result = alert_engine.generate_alerts(
        api_data=api_data,
        include_details=include_details,
        max_alerts=max_alerts,
        department=department,
        severity=severity,
        include_inactive=include_inactive
    )

    # Full filtered alert items for persistent storage
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
        "run_id": run_id,
        "result": alert_result
    }


@app.get("/alerts/history")
async def get_alert_history(limit: int = 10):
    """
    Returns recent alert scan history.

    This is useful for dashboard history:
    - when alert scans happened
    - how many alerts were found
    - severity counts
    - department counts
    """

    safe_limit = max(1, min(limit, 100))

    history = alert_repo.get_recent_alert_runs(limit=safe_limit)

    return {
        "status": "success",
        "total": len(history),
        "history": history
    }


@app.get("/alerts/latest")
async def get_latest_alert_run(
    limit: int = 100,
    department: Optional[str] = None,
    severity: Optional[str] = None
):
    """
    Returns the latest saved alert run with limited alert items.

    Optional filters:
    - department=Fleet Department
    - severity=critical
    - limit=100
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


@app.get("/alerts/history/{run_id}")
async def get_alert_run_details(
    run_id: str,
    limit: int = 100,
    department: Optional[str] = None,
    severity: Optional[str] = None
):
    """
    Returns one saved alert run with limited alert items.

    Optional filters:
    - department=Fleet Department
    - severity=critical
    - limit=100
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


@app.get("/logs/recent")
async def get_recent_logs(limit: int = 10):
    """
    Returns recent query logs.
    """

    safe_limit = max(1, min(limit, 50))

    logs = log_repo.get_recent_logs(limit=safe_limit)

    return {
        "total": len(logs),
        "logs": logs
    }


@app.get("/logs/{request_id}")
async def get_log_by_request_id(request_id: str):
    """
    Returns full details of one logged query.
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
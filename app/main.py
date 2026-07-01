import asyncio
import os
import time
from typing import Any, Optional
from uuid import uuid4

from dotenv import load_dotenv

load_dotenv()

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import uvicorn

from app.agent import BykeManiaAgent
from app.storage.log_repository import AgentLogRepository
from app.storage.alert_repository import AlertRepository
from app.tools.optimized_api import call_sir_optimized_api_with_metadata
from app.services.alert_engine import AlertEngine
from app.services.scheduler_service import SchedulerService
from app.security.api_key import verify_api_key


APP_VERSION = "0.1.4"


def get_environment() -> str:
    """
    Returns current app environment.
    Example:
    - development
    - production
    """

    return os.getenv("ENVIRONMENT", "development").strip().lower()


def is_production() -> bool:
    """
    Returns True when app is running in production.
    """

    return get_environment() == "production"


def get_env_int(
    key: str,
    default: int,
    minimum: int = 1,
    maximum: int = 600
) -> int:
    """
    Safely reads integer config values from environment variables.

    Example:
    CHAT_TIMEOUT_SECONDS=60
    """

    try:
        value = int(os.getenv(key, str(default)))
        return max(minimum, min(value, maximum))

    except Exception:
        return default


def get_chat_timeout_seconds() -> int:
    """
    Timeout for /chat requests.
    """

    return get_env_int(
        key="CHAT_TIMEOUT_SECONDS",
        default=60,
        minimum=5,
        maximum=180
    )


def get_alert_run_timeout_seconds() -> int:
    """
    Timeout for /alerts/run requests.
    """

    return get_env_int(
        key="ALERT_RUN_TIMEOUT_SECONDS",
        default=120,
        minimum=10,
        maximum=300
    )


def get_scheduler_manual_run_timeout_seconds() -> int:
    """
    Timeout for /scheduler/run-now requests.
    """

    return get_env_int(
        key="SCHEDULER_MANUAL_RUN_TIMEOUT_SECONDS",
        default=120,
        minimum=10,
        maximum=300
    )


def get_cors_origins() -> list[str]:
    """
    Reads allowed CORS origins from environment variable.

    Example:
    CORS_ORIGINS=http://localhost:3000,https://your-frontend.com
    """

    raw_origins = os.getenv("CORS_ORIGINS", "").strip()

    if raw_origins:
        return [
            origin.strip()
            for origin in raw_origins.split(",")
            if origin.strip()
        ]

    if is_production():
        return [
            "https://bykemania-agent-api.onrender.com"
        ]

    return [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:8000",
        "http://localhost:8000"
    ]


def get_request_id(request: Request) -> str:
    """
    Gets request ID from request state or headers.
    """

    request_id = getattr(request.state, "request_id", None)

    if request_id:
        return request_id

    return request.headers.get("x-request-id") or str(uuid4())


def build_error_response(
    request: Request,
    status_code: int,
    message: str,
    code: str,
    details: Optional[Any] = None,
    expose_details_in_production: bool = False
) -> JSONResponse:
    """
    Builds a consistent API error response.

    Production behavior:
    - hides internal details by default
    - keeps public message and request_id
    """

    request_id = get_request_id(request)

    error_data: dict[str, Any] = {
        "code": code
    }

    if details is not None and (not is_production() or expose_details_in_production):
        error_data["details"] = details

    return JSONResponse(
        status_code=status_code,
        content={
            "status": "error",
            "message": message,
            "error": error_data,
            "request_id": request_id
        },
        headers={
            "X-Request-ID": request_id
        }
    )


def build_timeout_response(
    request: Request,
    message: str,
    code: str,
    timeout_seconds: int
) -> JSONResponse:
    """
    Builds a standard timeout response.
    """

    return build_error_response(
        request=request,
        status_code=504,
        message=message,
        code=code,
        details={
            "timeout_seconds": timeout_seconds
        },
        expose_details_in_production=True
    )


def get_public_backend_error(api_result: dict[str, Any]) -> dict[str, Any]:
    """
    Returns backend API error safely.

    In production:
    - do not expose raw internal API error text
    - keep status code only

    In development:
    - expose raw error for debugging
    """

    safe_error = {
        "api_status_code": api_result.get("status_code")
    }

    if not is_production():
        safe_error["raw_error"] = api_result.get("error")

    return safe_error


app = FastAPI(
    title="BykeMania AI Agent",
    description="Natural Language AI Agent for BykeMania Operations",
    version=APP_VERSION,

    # Keep Swagger/OpenAPI available on Render
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_cors_origins(),
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_request_metadata(request: Request, call_next):
    """
    Adds request tracking metadata.

    Every response receives:
    - X-Request-ID
    - X-Process-Time-MS
    """

    request_id = request.headers.get("x-request-id") or str(uuid4())
    request.state.request_id = request_id

    start_time = time.perf_counter()

    try:
        response = await call_next(request)

    except Exception as exc:
        process_time_ms = round(
            (time.perf_counter() - start_time) * 1000,
            2
        )

        print(
            "[Unhandled Error]",
            {
                "request_id": request_id,
                "path": str(request.url.path),
                "method": request.method,
                "error_type": type(exc).__name__,
                "error": str(exc),
                "process_time_ms": process_time_ms
            }
        )

        public_message = "Internal server error"

        if not is_production():
            public_message = f"{type(exc).__name__}: {str(exc)}"

        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "message": public_message,
                "error": {
                    "code": "INTERNAL_SERVER_ERROR"
                },
                "request_id": request_id
            },
            headers={
                "X-Request-ID": request_id,
                "X-Process-Time-MS": str(process_time_ms)
            }
        )

    process_time_ms = round(
        (time.perf_counter() - start_time) * 1000,
        2
    )

    response.headers["X-Request-ID"] = request_id
    response.headers["X-Process-Time-MS"] = str(process_time_ms)

    return response


@app.exception_handler(HTTPException)
async def http_exception_handler(
    request: Request,
    exc: HTTPException
):
    """
    Standardizes HTTPException responses.

    Example:
    - 400 empty query
    - 401/403 invalid API key
    - 404 not found
    """

    detail = exc.detail

    if isinstance(detail, str):
        message = detail
    else:
        message = "Request failed."

    if exc.status_code >= 500 and is_production():
        message = "Internal server error"

    headers = dict(exc.headers or {})
    headers["X-Request-ID"] = get_request_id(request)

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "status": "error",
            "message": message,
            "error": {
                "code": "HTTP_EXCEPTION"
            },
            "request_id": get_request_id(request)
        },
        headers=headers
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError
):
    """
    Standardizes validation errors.

    Example:
    - missing query field in /chat body
    - wrong JSON type
    """

    details = exc.errors()

    return build_error_response(
        request=request,
        status_code=422,
        message="Invalid request data.",
        code="VALIDATION_ERROR",
        details=details,
        expose_details_in_production=True
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
    Public health/info endpoint.

    This endpoint is intentionally not API-key protected.
    """

    return {
        "message": "BykeMania AI Agent is running 🚀",
        "status": "healthy",
        "version": APP_VERSION,
        "environment": get_environment(),
        "docs": "/docs",
        "openapi_schema": "/openapi.json",
        "timeout_settings": {
            "chat_timeout_seconds": get_chat_timeout_seconds(),
            "alert_run_timeout_seconds": get_alert_run_timeout_seconds(),
            "scheduler_manual_run_timeout_seconds": get_scheduler_manual_run_timeout_seconds()
        },
        "security": {
            "protected_endpoints_require": "x-api-key header"
        },
        "available_endpoints": {
            "health": "GET /health",
            "ready": "GET /ready",

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


@app.get("/health")
async def health():
    """
    Lightweight public health check.

    Use this for uptime checks and Render health checks.
    """

    return {
        "status": "healthy",
        "service": "bykemania-agent-api",
        "version": APP_VERSION,
        "environment": get_environment()
    }


@app.get("/ready")
async def ready(request: Request):
    """
    Readiness check.

    This confirms that core repositories can initialize.
    It does not call the private fleet backend.
    """

    try:
        log_repo.get_recent_logs(limit=1)

        return {
            "status": "ready",
            "service": "bykemania-agent-api",
            "database": "connected",
            "version": APP_VERSION
        }

    except Exception as exc:
        print(
            "[Readiness Error]",
            {
                "request_id": get_request_id(request),
                "error_type": type(exc).__name__,
                "error": str(exc)
            }
        )

        return build_error_response(
            request=request,
            status_code=503,
            message="Service is not ready.",
            code="READINESS_CHECK_FAILED",
            details={
                "error_type": type(exc).__name__,
                "error": str(exc)
            }
        )


@app.post(
    "/chat",
    dependencies=[Depends(verify_api_key)]
)
async def chat(
    request: Request,
    chat_request: ChatRequest
):
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

    cleaned_query = chat_request.query.strip()

    if not cleaned_query:
        raise HTTPException(
            status_code=400,
            detail="Query cannot be empty."
        )

    if len(cleaned_query) > 1000:
        raise HTTPException(
            status_code=400,
            detail="Query is too long. Please keep it under 1000 characters."
        )

    timeout_seconds = get_chat_timeout_seconds()

    try:
        response_data = await asyncio.wait_for(
            agent.process_query(cleaned_query),
            timeout=timeout_seconds
        )

    except asyncio.TimeoutError:
        return build_timeout_response(
            request=request,
            message="Chat request timed out. Please try again with a simpler query.",
            code="CHAT_TIMEOUT",
            timeout_seconds=timeout_seconds
        )

    return {
        "query": cleaned_query,
        "response": response_data,
        "status": "success"
    }


@app.get(
    "/alerts/run",
    dependencies=[Depends(verify_api_key)]
)
async def run_alert_check(
    request: Request,
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

    timeout_seconds = get_alert_run_timeout_seconds()

    try:
        api_result = await asyncio.wait_for(
            call_sir_optimized_api_with_metadata(),
            timeout=timeout_seconds
        )

    except asyncio.TimeoutError:
        return build_timeout_response(
            request=request,
            message="Alert run timed out while fetching fleet data.",
            code="ALERT_RUN_TIMEOUT",
            timeout_seconds=timeout_seconds
        )

    if not api_result.get("success"):
        return build_error_response(
            request=request,
            status_code=502,
            message="Could not fetch data from optimized API.",
            code="BACKEND_API_ERROR",
            details=get_public_backend_error(api_result)
        )

    api_data = api_result.get("data", [])

    if not isinstance(api_data, list):
        return build_error_response(
            request=request,
            status_code=502,
            message="Backend API returned unexpected data format.",
            code="INVALID_BACKEND_DATA",
            details={
                "data_type": str(type(api_data))
            }
        )

    safe_max_alerts = max(1, min(max_alerts, 100))

    alert_result = alert_engine.generate_alerts(
        api_data=api_data,
        include_details=include_details,
        max_alerts=safe_max_alerts,
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

    safe_limit = max(1, min(limit, 500))

    latest = alert_repo.get_latest_alert_run(
        limit=safe_limit,
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

    safe_limit = max(1, min(limit, 500))

    alert_run = alert_repo.get_alert_run_by_id(
        run_id=run_id,
        limit=safe_limit,
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

    safe_limit = max(1, min(limit, 500))

    data = alert_repo.get_department_dashboard(
        department_name=department_name,
        run_id=run_id,
        limit=safe_limit,
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
async def scheduler_run_now(
    request: Request,
    force: bool = False
):
    """
    Manually triggers the same alert check used by the scheduler.

    Protected by x-api-key.

    Cooldown protection:
    - by default it skips if a recent run already exists
    - use force=true to bypass cooldown
    """

    timeout_seconds = get_scheduler_manual_run_timeout_seconds()

    try:
        result = await asyncio.wait_for(
            scheduler_service.run_alert_check_now(
                triggered_by="manual_endpoint",
                force=force
            ),
            timeout=timeout_seconds
        )

    except asyncio.TimeoutError:
        return build_timeout_response(
            request=request,
            message="Manual scheduler run timed out.",
            code="SCHEDULER_MANUAL_RUN_TIMEOUT",
            timeout_seconds=timeout_seconds
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
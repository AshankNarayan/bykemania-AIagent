# BykeMania AI Operations Agent

Production-ready FastAPI backend for BykeMania operations, fleet intelligence, alert generation, and dashboard APIs.

The system allows internal teams to ask natural-language operational questions, fetch live fleet data, generate department-wise alerts, store alert history, and expose dashboard-ready APIs through a secured backend service.

---

## 1. Project Overview

The BykeMania AI Operations Agent is designed as an internal operations assistant for a bike rental business.

It connects natural-language queries with live fleet data and operational workflows. The backend is deployed as a cloud API and can be used through Swagger, frontend dashboards, internal tools, or future automation layers.

### Core capabilities

- Natural-language AI chat for operational queries
- Live fleet availability responses
- Active location and model discovery
- Department-wise alert generation
- Alert history storage
- Dashboard summary APIs
- Query and response logging
- Scheduler support for automated alert runs
- API key authentication
- PostgreSQL production storage
- Health checks and readiness checks
- Standardized error handling
- Request tracing
- Timeout protection
- Basic rate limiting

---

## 2. Current Production Status

```text
Version: 0.1.5
Status: Production-ready MVP
Deployment: Render
Database: Neon PostgreSQL
Scheduler: Disabled by default for safety
```

### Stable production checklist

```text
✅ FastAPI backend deployed
✅ Render deployment working
✅ Neon PostgreSQL connected
✅ Swagger/OpenAPI working
✅ API key authentication working
✅ /chat working
✅ /dashboard APIs working
✅ /health and /ready working
✅ standardized error handling
✅ request ID tracking
✅ timeout protection
✅ rate limiting
✅ scheduler safely disabled
```

---

## 3. Live Deployment

### Backend URL

```text
https://bykemania-agent-api.onrender.com
```

### Swagger API Documentation

```text
https://bykemania-agent-api.onrender.com/docs
```

### OpenAPI Schema

```text
https://bykemania-agent-api.onrender.com/openapi.json
```

---

## 4. Tech Stack

| Layer | Technology |
|---|---|
| Backend framework | FastAPI |
| Server | Uvicorn |
| Language | Python |
| Database | Neon PostgreSQL |
| Local database fallback | SQLite |
| AI / LLM | Groq API |
| Validation | Pydantic |
| Scheduling | APScheduler |
| HTTP clients | HTTPX / Requests |
| Fuzzy matching | RapidFuzz |
| Deployment | Render |
| Source control | GitHub |

---

## 5. System Architecture

```text
User / Swagger / Future Frontend
        |
        v
FastAPI Backend
        |
        |-- API Key Security
        |-- Request Metadata Middleware
        |-- Error Handling
        |-- Timeout Protection
        |-- Rate Limiting
        |
        v
BykeMania Agent
        |
        |-- Query Parser
        |-- LLM Router
        |-- Response Formatter
        |
        v
Private Fleet Backend API
        |
        v
Fleet Data / Availability Data


Alert Engine
        |
        |-- Service Alerts
        |-- Fleet Alerts
        |-- Recovery Alerts
        |-- Compliance Alerts
        |
        v
Alert Repository
        |
        v
Neon PostgreSQL


Dashboard APIs
        |
        v
Frontend / Internal Dashboard / Swagger
```

---

## 6. Project Structure

```text
bykemania-agent/
│
├── app/
│   ├── main.py
│   ├── agent.py
│   ├── config.py
│   │
│   ├── data/
│   │   ├── locations.csv
│   │   └── models.csv
│   │
│   ├── llm/
│   │   ├── gpt_client.py
│   │   ├── llama_client.py
│   │   └── router.py
│   │
│   ├── prompts/
│   │   ├── system_prompts.py
│   │   └── system_prompts.yaml
│   │
│   ├── security/
│   │   ├── __init__.py
│   │   └── api_key.py
│   │
│   ├── services/
│   │   ├── alert_engine.py
│   │   ├── matcher.py
│   │   ├── query_parser.py
│   │   ├── response_formatter.py
│   │   ├── scheduler_service.py
│   │   └── utilisation_parser.py
│   │
│   ├── storage/
│   │   ├── __init__.py
│   │   ├── database.py
│   │   ├── log_repository.py
│   │   └── alert_repository.py
│   │
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── api_client.py
│   │   └── optimized_api.py
│   │
│   └── utils/
│       ├── date_utils.py
│       └── llm_client.py
│
├── .env.example
├── .gitignore
├── README.md
├── requirements.txt
├── Procfile
└── render.yaml
```

---

## 7. Main Features

### 7.1 AI Chat

The `/chat` endpoint accepts natural-language queries and returns structured operational answers.

Example queries:

```text
hello
Tell me all the active locations
total Activa at Koramangala today
What does force block mean?
```

The agent can handle:

- Fleet availability questions
- Location-based availability
- Model-based availability
- Active location listing
- Vehicle model listing
- Department-related questions
- Alert explanations
- General operational questions

---

### 7.2 Alert Engine

The alert engine scans fleet data and generates department-specific alerts.

Supported departments:

- Service Department
- Fleet Department
- Recovery Department
- Compliance Department

Supported alert categories:

- Service due
- Service overdue
- Force block
- Booking recovered
- Insurance expired
- Emission expired
- Compliance-related alerts
- Fleet operational issues

---

### 7.3 Dashboard APIs

The backend exposes APIs that can directly support a future frontend dashboard.

```http
GET /dashboard/summary
GET /dashboard/departments
GET /dashboard/department/{department_name}
```

These APIs provide:

- Overall alert summary
- Department-wise alert cards
- Department-specific alert details
- Severity filtering
- Latest alert run data

---

### 7.4 Logging

The system logs important request lifecycle data.

Logged fields include:

- Request ID
- Timestamp
- User query
- Parsed intent
- Model name
- Location name
- Date string
- Backend API URL/status/success flag
- Backend API response
- Final formatted response
- Status
- Error message

Production logs are stored in PostgreSQL.

---

### 7.5 Scheduler Support

The project includes scheduler support using APScheduler.

The scheduler can automatically run alert checks at a fixed interval, but it is currently recommended to keep it disabled in production until alert volume, notification delivery, and database write volume are fully reviewed.

Recommended production setting:

```env
ALERT_SCHEDULER_ENABLED=false
```

---

## 8. API Security

Most operational endpoints are protected using an API key.

The key must be sent using the request header:

```http
x-api-key: your_private_api_key
```

### Protected endpoints

```http
POST /chat
GET /logs/recent
GET /logs/{request_id}
GET /alerts/run
GET /alerts/history
GET /alerts/latest
GET /alerts/history/{run_id}
GET /dashboard/summary
GET /dashboard/departments
GET /dashboard/department/{department_name}
GET /scheduler/status
POST /scheduler/run-now
```

### Public endpoints

```http
GET /
HEAD /
GET /health
GET /ready
GET /docs
GET /openapi.json
```

### Secret handling rules

Never commit or expose:

```text
.env
API keys
Database URLs
Private backend URLs
Groq keys
Render environment values
Neon connection strings
```

If any secret is exposed:

1. Rotate the secret immediately.
2. Update local `.env`.
3. Update Render environment variables.
4. Redeploy the service.
5. Test the service with the new secret.

---

## 9. Production Hardening

### 9.1 Health Check

```http
GET /health
```

Purpose:

- Confirms the backend service is alive
- Useful for uptime monitoring
- Does not require API key

Example response:

```json
{
  "status": "healthy",
  "service": "bykemania-agent-api",
  "version": "0.1.5",
  "environment": "production"
}
```

---

### 9.2 Readiness Check

```http
GET /ready
```

Purpose:

- Confirms database/repository layer is reachable
- Does not call the private fleet backend
- Useful before routing traffic to the service

Example response:

```json
{
  "status": "ready",
  "service": "bykemania-agent-api",
  "database": "connected",
  "version": "0.1.5"
}
```

---

### 9.3 Request Metadata

Every response includes:

```http
X-Request-ID
X-Process-Time-MS
```

These headers help trace requests during debugging and production monitoring.

---

### 9.4 Standard Error Format

All handled errors follow a consistent structure.

Example:

```json
{
  "status": "error",
  "message": "Query cannot be empty.",
  "error": {
    "code": "HTTP_EXCEPTION"
  },
  "request_id": "generated-request-id"
}
```

Benefits:

- Easier frontend handling
- Easier debugging
- Safer production errors
- Less risk of exposing internal stack traces

---

### 9.5 Timeout Protection

Timeouts prevent slow external calls from hanging the API.

Configured through:

```env
CHAT_TIMEOUT_SECONDS=60
ALERT_RUN_TIMEOUT_SECONDS=120
SCHEDULER_MANUAL_RUN_TIMEOUT_SECONDS=120
```

Applied to:

```http
POST /chat
GET /alerts/run
POST /scheduler/run-now
```

---

### 9.6 Rate Limiting

Basic in-memory rate limiting protects against accidental spam and excessive usage.

Configured through:

```env
CHAT_RATE_LIMIT_PER_MINUTE=30
ALERT_RUN_RATE_LIMIT_PER_HOUR=6
SCHEDULER_RUN_RATE_LIMIT_PER_HOUR=6
```

Applied to:

```http
POST /chat
GET /alerts/run
POST /scheduler/run-now
```

Current implementation is in-memory and works well for a single Render instance.

If the service is later scaled to multiple instances, rate limiting should be moved to Redis or PostgreSQL.

---

## 10. Environment Variables

### Required variables

```env
ENVIRONMENT=production

DATABASE_TYPE=postgres
DATABASE_URL=your_postgres_database_url_here

GROQ_API_KEY=your_groq_api_key_here
APP_API_KEY=your_private_app_api_key_here
SIR_API_URL=your_private_backend_api_url_here

ALERT_SCHEDULER_ENABLED=false
ALERT_SCHEDULER_INTERVAL_MINUTES=120
ALERT_SCHEDULER_RUN_ON_STARTUP=false
ALERT_RUN_COOLDOWN_MINUTES=60

CHAT_TIMEOUT_SECONDS=60
ALERT_RUN_TIMEOUT_SECONDS=120
SCHEDULER_MANUAL_RUN_TIMEOUT_SECONDS=120

CHAT_RATE_LIMIT_PER_MINUTE=30
ALERT_RUN_RATE_LIMIT_PER_HOUR=6
SCHEDULER_RUN_RATE_LIMIT_PER_HOUR=6

CORS_ORIGINS=https://bykemania-agent-api.onrender.com
```

---

## 11. Database Configuration

### 11.1 Local SQLite

Recommended for quick local development:

```env
DATABASE_TYPE=sqlite
DATABASE_URL=sqlite:///app/storage/agent_logs.sqlite3
```

---

### 11.2 Production PostgreSQL

Recommended for Render deployment:

```env
DATABASE_TYPE=postgres
DATABASE_URL=postgresql://username:password@host/database?sslmode=require
```

Production database currently uses Neon PostgreSQL.

Never expose the real PostgreSQL connection string.

---

## 12. Local Development Setup

### 12.1 Clone repository

```powershell
git clone https://github.com/AshankNarayan/bykemania-AIagent.git
cd bykemania-AIagent
```

---

### 12.2 Create virtual environment

```powershell
python -m venv venv
venv\Scripts\activate
```

---

### 12.3 Install dependencies

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

---

### 12.4 Create `.env`

Copy:

```text
.env.example
```

to:

```text
.env
```

Then fill real local values.

Do not commit `.env`.

---

### 12.5 Run locally

```powershell
python -m uvicorn app.main:app --reload
```

Local API:

```text
http://127.0.0.1:8000
```

Local Swagger:

```text
http://127.0.0.1:8000/docs
```

---

## 13. Deployment on Render

### Build command

```bash
pip install -r requirements.txt
```

### Start command

```bash
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

### Runtime

```text
Python 3
```

### Root directory

```text
Leave blank
```

### Branch

```text
main
```

### Required Render environment variables

```env
ENVIRONMENT=production
DATABASE_TYPE=postgres
DATABASE_URL=your_neon_postgres_url
GROQ_API_KEY=your_groq_api_key
APP_API_KEY=your_private_app_api_key
SIR_API_URL=your_private_backend_api_url

ALERT_SCHEDULER_ENABLED=false
ALERT_SCHEDULER_INTERVAL_MINUTES=120
ALERT_SCHEDULER_RUN_ON_STARTUP=false
ALERT_RUN_COOLDOWN_MINUTES=60

CHAT_TIMEOUT_SECONDS=60
ALERT_RUN_TIMEOUT_SECONDS=120
SCHEDULER_MANUAL_RUN_TIMEOUT_SECONDS=120

CHAT_RATE_LIMIT_PER_MINUTE=30
ALERT_RUN_RATE_LIMIT_PER_HOUR=6
SCHEDULER_RUN_RATE_LIMIT_PER_HOUR=6

CORS_ORIGINS=https://bykemania-agent-api.onrender.com
```

---

## 14. API Usage Guide

### 14.1 Root endpoint

```http
GET /
```

Returns basic service info, version, environment, timeout settings, rate limit settings, and available endpoints.

---

### 14.2 Health check

```http
GET /health
```

No API key required.

---

### 14.3 Readiness check

```http
GET /ready
```

No API key required.

---

### 14.4 Chat

```http
POST /chat
x-api-key: your_api_key
Content-Type: application/json
```

Request body:

```json
{
  "query": "Tell me all the active locations"
}
```

Example response structure:

```json
{
  "query": "Tell me all the active locations",
  "response": {
    "answer_type": "locations",
    "summary": "Found active locations.",
    "request_id": "generated-request-id",
    "timestamp_utc": "2026-07-02T00:00:00+00:00"
  },
  "status": "success"
}
```

---

### 14.5 Recent logs

```http
GET /logs/recent
x-api-key: your_api_key
```

Optional query parameter:

```text
limit=10
```

---

### 14.6 Full log by request ID

```http
GET /logs/{request_id}
x-api-key: your_api_key
```

---

### 14.7 Run alerts

```http
GET /alerts/run
x-api-key: your_api_key
```

Optional query parameters:

```text
include_details=false
max_alerts=20
department=Service
severity=HIGH
include_inactive=false
force=false
```

Force run:

```http
GET /alerts/run?force=true
x-api-key: your_api_key
```

Use `force=true` carefully because alert runs can create many database rows.

---

### 14.8 Alert history

```http
GET /alerts/history
x-api-key: your_api_key
```

Optional query parameter:

```text
limit=10
```

---

### 14.9 Latest alert run

```http
GET /alerts/latest
x-api-key: your_api_key
```

Optional query parameters:

```text
limit=100
department=Service
severity=HIGH
```

---

### 14.10 Alert run details

```http
GET /alerts/history/{run_id}
x-api-key: your_api_key
```

Optional query parameters:

```text
limit=100
department=Service
severity=HIGH
```

---

### 14.11 Dashboard summary

```http
GET /dashboard/summary
x-api-key: your_api_key
```

---

### 14.12 Dashboard departments

```http
GET /dashboard/departments
x-api-key: your_api_key
```

Optional query parameter:

```text
run_id=your_run_id
```

---

### 14.13 Dashboard department detail

```http
GET /dashboard/department/{department_name}
x-api-key: your_api_key
```

Optional query parameters:

```text
run_id=your_run_id
limit=50
severity=HIGH
```

---

### 14.14 Scheduler status

```http
GET /scheduler/status
x-api-key: your_api_key
```

---

### 14.15 Manual scheduler run

```http
POST /scheduler/run-now
x-api-key: your_api_key
```

Force run:

```http
POST /scheduler/run-now?force=true
x-api-key: your_api_key
```

---

## 15. Testing Checklist

### Local test commands

```powershell
python -m py_compile app/main.py
python -c "from app.main import app; print(app.version); print(app.docs_url); print(app.openapi_url)"
python -m uvicorn app.main:app --reload
```

### Local endpoint tests

```text
GET /
GET /health
GET /ready
POST /chat
GET /logs/recent
GET /scheduler/status
GET /dashboard/summary
```

### Production endpoint tests

```text
GET /
GET /health
GET /ready
POST /chat
GET /logs/recent
GET /dashboard/summary
GET /scheduler/status
```

---

## 16. Git Workflow

Check changes:

```powershell
git status
```

Stage changes:

```powershell
git add README.md .env.example
```

Commit:

```powershell
git commit -m "Add production documentation"
```

Push:

```powershell
git push
```

---

## 17. Operational Notes

### Scheduler

Keep scheduler disabled until the production alert workflow is finalized.

```env
ALERT_SCHEDULER_ENABLED=false
```

Enable only after:

- alert volume is reviewed
- database write volume is acceptable
- notification delivery is ready
- cooldown rules are confirmed
- team workflow is finalized

---

### Alert runs

Alert runs may write many rows to the database.

Use this carefully:

```http
GET /alerts/run?force=true
```

The system includes cooldown and rate limiting, but forced alert runs should still be used responsibly.

---

### Rate limiting

Current rate limiting is in-memory.

This is acceptable for:

- MVP
- one Render instance
- internal usage
- early production testing

Move to Redis/PostgreSQL-backed rate limiting if:

- multiple instances are used
- public frontend traffic increases
- API key sharing becomes common
- stricter audit requirements appear

---

### CORS

Current production CORS should include the backend domain and future frontend domain.

Example:

```env
CORS_ORIGINS=https://your-frontend-domain.com,https://bykemania-agent-api.onrender.com
```

---

## 18. Troubleshooting

### Swagger does not load

Check:

```text
/openapi.json
```

If it returns 404, confirm FastAPI has:

```python
openapi_url="/openapi.json"
```

---

### Protected endpoint returns auth error

Check:

```text
x-api-key
```

Make sure the key matches the current `APP_API_KEY` in Render environment variables.

---

### Database connection fails

Check:

```env
DATABASE_TYPE=postgres
DATABASE_URL=postgresql://username:password@host/database?sslmode=require
```

Also confirm the database password was not rotated without updating Render.

---

### Render deploy fails

Check Render logs for:

```text
ModuleNotFoundError
Database connection error
APP_API_KEY missing
SIR_API_URL missing
Application failed to bind to port
```

Correct start command:

```bash
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

---

### `/alerts/run` is slow

Expected causes:

- private fleet backend is slow
- large fleet data response
- many alert items generated
- database writes taking time

The endpoint has timeout protection and rate limiting.

---

## 19. Future Roadmap

Planned improvements:

```text
1. Frontend dashboard
2. Department-specific dashboard UI
3. Email or WhatsApp alert delivery
4. Admin panel for operations team
5. Redis/PostgreSQL-backed distributed rate limiting
6. Better monitoring and alerting
7. Automated test suite
8. CI/CD checks before deployment
9. Role-based access control
10. Separate staging and production environments
```

---

## 20. Maintainer

```text
Ashank Narayan
B.Tech ECSE, KIIT University
AI Operations / Agentic AI Intern Project
```
# BykeMania AI Agent

A FastAPI-based AI operations assistant for BykeMania.

The system allows operations users to ask natural-language fleet queries, generate department-wise alerts, store alert history, view dashboard-ready APIs, and run scheduled alert checks with cooldown protection.

---

## Features

- Natural-language query endpoint
- Optimized backend API integration
- Query and API response logging
- Department-wise alert generation
- Alert history storage
- Dashboard-ready API endpoints
- Manual and scheduled alert checks
- Cooldown protection to prevent duplicate alert runs
- API-key protection using `x-api-key`

---

## Tech Stack

- Python
- FastAPI
- Uvicorn
- SQLite for local MVP storage
- APScheduler for scheduled alert checks
- Groq/Llama for LLM support
- Python dotenv for environment variables

---

## Project Structure

```text
bykemania-agent/
│
├── .env.example
├── .gitignore
├── README.md
├── requirements.txt
│
└── app/
    ├── __init__.py
    ├── main.py
    ├── agent.py
    ├── config.py
    │
    ├── data/
    │   ├── locations.csv
    │   └── models.csv
    │
    ├── llm/
    │   ├── gpt_client.py
    │   ├── llama_client.py
    │   └── router.py
    │
    ├── prompts/
    │   ├── system_prompts.py
    │   └── system_prompts.yaml
    │
    ├── security/
    │   ├── __init__.py
    │   └── api_key.py
    │
    ├── services/
    │   ├── alert_engine.py
    │   ├── matcher.py
    │   ├── query_parser.py
    │   ├── response_formatter.py
    │   └── scheduler_service.py
    │
    ├── storage/
    │   ├── __init__.py
    │   ├── database.py
    │   ├── log_repository.py
    │   └── alert_repository.py
    │
    ├── tools/
    │   ├── __init__.py
    │   ├── api_client.py
    │   └── optimized_api.py
    │
    └── utils/
        ├── date_utils.py
        └── llm_client.py

---

## Cloud Deployment: Render

This project can be deployed as a FastAPI web service.

### Render settings

Use the following settings:

```text
Language: Python 3
Build Command: pip install -r requirements.txt
Start Command: uvicorn app.main:app --host 0.0.0.0 --port $PORT
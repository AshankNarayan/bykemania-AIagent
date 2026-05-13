# app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

# IMPORTANT: Use absolute imports when running with python -m
from app.services.agent import BykeManiaAgent

app = FastAPI(
    title="BykeMania OpsAI",
    description="Natural Language AI Agent for Operations Team",
    version="0.1.0"
)

# CORS (for future frontend / Streamlit / Slack)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize agent once at startup
agent = BykeManiaAgent()

class ChatRequest(BaseModel):
    query: str

@app.get("/")
async def root():
    return {
        "message": "BykeMania OpsAI is running 🚀",
        "status": "healthy",
        "version": "0.1.0"
    }

@app.post("/chat")
async def chat(request: ChatRequest):
    """Main endpoint for all natural language operational queries"""
    try:
        response_text = await agent.process_query(request.query)
        return {
            "query": request.query,
            "response": response_text,
            "status": "success"
        }
    except Exception as e:
        print(f"[ERROR] {e}")
        return {
            "query": request.query,
            "response": "Sorry, something went wrong while processing your query.",
            "status": "error"
        }


if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
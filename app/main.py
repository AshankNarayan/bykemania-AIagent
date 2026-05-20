import sys
import os

# CRITICAL FIX FOR WINDOWS IMPORT ISSUES
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

# Correct import - agent.py is in tools folder
from app.tools.agent import BykeManiaAgent

app = FastAPI(
    title="BykeMania AI Agent",
    description="Natural Language AI Agent for BykeMania",
    version="0.1.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

agent = BykeManiaAgent()

class ChatRequest(BaseModel):
    query: str

@app.get("/")
async def root():
    return {"message": "BykeMania AI Agent is running 🚀", "status": "healthy"}

@app.post("/chat")
async def chat(request: ChatRequest):
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
            "response": "Sorry, something went wrong.",
            "status": "error"
        }

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
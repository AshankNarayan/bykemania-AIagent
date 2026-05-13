# app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
import uvicorn

from app.services.agent import BykeManiaAgent

app = FastAPI(
    title="BykeMania OpsAI",
    description="Natural Language AI Agent for BykeMania Operations Team",
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
    return {"message": "BykeMania OpsAI is running 🚀"}

@app.post("/chat")
async def chat(request: ChatRequest):
    """Returns CLEAN readable text (best for Swagger UI)"""
    try:
        response_text = await agent.process_query(request.query)
        
        # This makes the response look clean in Swagger
        return PlainTextResponse(
            content=response_text,
            media_type="text/plain"
        )
        
    except Exception as e:
        print(f"[ERROR] {e}")
        return PlainTextResponse(
            content="Sorry, something went wrong while processing your query.",
            status_code=500
        )


if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
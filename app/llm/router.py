# app/llm/router.py
from dotenv import load_dotenv
import os
from groq import AsyncGroq
from openai import AsyncOpenAI   # for future fallback

load_dotenv()

class LLMRouter:
    def __init__(self):
        self.groq_client = AsyncGroq(api_key=os.getenv("GROQ_API_KEY"))
        # Optional: fallback client
        # self.openai_client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    
    async def get_llm_client(self):
        """Returns the primary LLM client (Groq for now)"""
        return self.groq_client


# Singleton instance
_llm_router = LLMRouter()

async def get_llm_client():
    """Global helper function used by other modules"""
    return await _llm_router.get_llm_client()


# Quick test
if __name__ == "__main__":
    import asyncio
    async def test():
        client = await get_llm_client()
        print("✅ Groq client connected successfully")
        print(type(client))
    asyncio.run(test())
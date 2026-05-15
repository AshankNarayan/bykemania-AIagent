# app/services/agent.py
from .query_parser import QueryParser, QueryIntent
from .response_formatter import ResponseFormatter
from ..tools.api_client import ApiClient
from ..services.matcher import Matcher
from ..llm.router import get_llm_client
import asyncio


class BykeManiaAgent:
    def __init__(self):
        self.parser = QueryParser()
        self.formatter = ResponseFormatter()
        self.api_client = ApiClient()
        self.matcher = Matcher()
        self.llm_client = None

    async def _get_llm(self):
        if self.llm_client is None:
            self.llm_client = await get_llm_client()
        return self.llm_client

    async def process_query(self, user_query: str) -> str:
        print(f"🔍 Processing query: {user_query}")

        # Step 1: Extract intent and entities
        query_intent: QueryIntent = await self.parser.parse(user_query)

        if query_intent.intent == "unknown":
            # Even for unknown intent, try to call API with whatever we extracted
            pass

        # Step 2: Resolve names
        model_id = self.matcher.match_model(query_intent.model_name) if query_intent.model_name else None
        location_id = self.matcher.match_location(query_intent.location_name) if query_intent.location_name else None

        # Step 3: Call real API
        try:
            api_data = await self.api_client.get_model_utilisation(
                model_id=model_id,
                location_id=location_id,
                date_str=query_intent.date_str
            )
        except Exception as e:
            print(f"[Agent] API Error: {e}")
            return "❌ The backend API is not responding right now. Please try again later."

        if not api_data:
            return f"No data found for **{query_intent.model_name or 'all models'}** at **{query_intent.location_name or 'all locations'}**."

        # Step 4: Try structured formatter first (for known cases)
        try:
            if query_intent.intent in ["get_availability", "get_utilization", "get_models_at_location"]:
                return self.formatter.format_availability_response(query_intent, api_data)
        except:
            pass

        # Step 5: Fallback - Let LLM generate response dynamically (this handles unknown queries)
        print("🤖 Using LLM to generate dynamic response...")
        llm = await self._get_llm()

        prompt = f"""
You are BykeMania OpsAI, an expert operations assistant.
User asked: "{user_query}"

Here is the raw data returned from the backend API:
{api_data}

Give a clear, professional, and easy-to-read answer.
Use markdown formatting. Be concise and helpful.
"""

        try:
            response = await llm.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=600
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            print(f"[LLM Fallback Error] {e}")
            return self.formatter.format_availability_response(query_intent, api_data)


# Quick test
if __name__ == "__main__":
    async def test():
        agent = BykeManiaAgent()
        result = await agent.process_query("Show all models at Koramangala today")
        print("\n" + "="*80)
        print(result)
        print("="*80)
    asyncio.run(test())
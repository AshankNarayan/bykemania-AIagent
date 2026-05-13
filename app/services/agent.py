# app/services/agent.py
from .query_parser import QueryParser, QueryIntent
from .response_formatter import ResponseFormatter
from ..tools.api_client import ApiClient
from ..services.matcher import Matcher   # assuming you have this
import asyncio


class BykeManiaAgent:
    def __init__(self):
        self.parser = QueryParser()
        self.formatter = ResponseFormatter()
        self.api_client = ApiClient()      # We'll improve this later
        self.matcher = Matcher()           # Your existing fuzzy matcher

    async def process_query(self, user_query: str) -> str:
        """
        Main workflow of the AI agent
        """
        print(f"🔍 Processing query: {user_query}")

        # Step 1: Parse natural language → Structured data
        query_intent: QueryIntent = await self.parser.parse(user_query)

        if query_intent.intent == "unknown":
            return "Sorry, I didn't understand the query. Can you please rephrase? (e.g. 'Show Activa at Koramangala today')"

        # Step 2: Resolve names to IDs using matcher
        model_id = None
        location_id = None

        if query_intent.model_name:
            model_id = self.matcher.match_model(query_intent.model_name)
        
        if query_intent.location_name:
            location_id = self.matcher.match_location(query_intent.location_name)

        # Step 3: Call API (for now using model-utilisation as example)
        try:
            api_data = await self.api_client.get_model_utilisation(
                model_id=model_id,
                location_id=location_id,
                date_str=query_intent.date_str
            )
        except Exception as e:
            print(f"[Agent] API Error: {e}")
            return "❌ Sorry, the backend API is not responding right now. Please try again later."

        # Step 4: Format nice response
        if query_intent.intent in ["get_availability", "get_utilization"]:
            response_text = self.formatter.format_availability_response(query_intent, api_data)
        else:
            response_text = "✅ Query understood but response format not implemented yet."

        return response_text


# For quick testing
if __name__ == "__main__":
    async def test():
        agent = BykeManiaAgent()
        result = await agent.process_query("Show Activa availability at Koramangala today")
        print("\n" + "="*50)
        print(result)
        print("="*50)

    asyncio.run(test())
import json
from typing import Optional, Literal

from pydantic import BaseModel, Field

from app.llm.router import get_llm_client


class QueryIntent(BaseModel):
    intent: Literal[
        "get_availability",
        "get_models_at_location",
        "get_utilization",
        "get_all_models",
        "get_locations",
        "general_chat",
        "unknown"
    ] = Field(..., description="Main intent of the query")

    model_name: Optional[str] = Field(
        None,
        description="Bike/scooter model name e.g. Activa, Access, Jupiter, KTM"
    )

    location_name: Optional[str] = Field(
        None,
        description="Location name e.g. Koramangala, Indiranagar, HSR Layout"
    )

    date_str: Optional[str] = Field(
        None,
        description="Date - keep as 'today', 'tomorrow', 'next week' or YYYY-MM-DD"
    )

    raw_query: str = Field(..., description="Original user query")


class QueryParser:
    """
    QueryParser converts natural language into an operational intent.

    Important:
    This parser should never break /chat.
    If strict parsing fails, it returns a safe fallback intent.
    """

    def _keyword_fallback(self, user_query: str) -> QueryIntent:
        """
        Simple deterministic fallback when LLM parsing fails
        or returns an invalid JSON/intent.
        """

        query = user_query.lower().strip()

        location_words = [
            "active location",
            "active locations",
            "all location",
            "all locations",
            "list locations",
            "show locations",
            "locations",
            "branches",
            "stations"
        ]

        model_words = [
            "all models",
            "models",
            "bike types",
            "scooter types",
            "vehicle types"
        ]

        availability_words = [
            "available",
            "availability",
            "total",
            "how many",
            "count",
            "at",
            "today",
            "tomorrow"
        ]

        utilization_words = [
            "utilization",
            "utilisation",
            "usage",
            "used",
            "fleet usage"
        ]

        greeting_words = [
            "hi",
            "hello",
            "hey",
            "good morning",
            "good evening"
        ]

        if any(word in query for word in location_words):
            return QueryIntent(
                intent="get_locations",
                model_name=None,
                location_name=None,
                date_str=None,
                raw_query=user_query
            )

        if any(word in query for word in model_words):
            return QueryIntent(
                intent="get_all_models",
                model_name=None,
                location_name=None,
                date_str=None,
                raw_query=user_query
            )

        if any(word in query for word in utilization_words):
            return QueryIntent(
                intent="get_utilization",
                model_name=None,
                location_name=None,
                date_str=None,
                raw_query=user_query
            )

        if any(word in query for word in availability_words):
            return QueryIntent(
                intent="get_availability",
                model_name=None,
                location_name=None,
                date_str=None,
                raw_query=user_query
            )

        if query in greeting_words or len(query.split()) <= 3:
            return QueryIntent(
                intent="general_chat",
                model_name=None,
                location_name=None,
                date_str=None,
                raw_query=user_query
            )

        return QueryIntent(
            intent="general_chat",
            model_name=None,
            location_name=None,
            date_str=None,
            raw_query=user_query
        )

    async def parse(self, user_query: str) -> QueryIntent:
        """
        Parses the user query into one allowed intent.

        This method never raises an exception to the agent.
        """

        system_prompt = """
You are a precise query parser for a bike rental operations AI agent.

You must return ONLY valid JSON.

Allowed intent values:
1. get_availability
   Use when user asks about available vehicles, count, total vehicles, model availability, bikes at a location, scooters for a date.

2. get_models_at_location
   Use when user asks what models are present at a specific location.

3. get_utilization
   Use when user asks about usage, utilization, booking usage, fleet usage.

4. get_all_models
   Use when user asks for all models, vehicle types, scooter types, bike types.

5. get_locations
   Use when user asks for all locations, active locations, branches, stations, city points.

6. general_chat
   Use when user asks general explanation, help, greeting, operational advice, department guidance, definitions, or anything that does not need live fleet data.

7. unknown
   Use only when the query is impossible to understand.

Rules:
- Never invent model or location.
- If model is missing, set model_name to null.
- If location is missing, set location_name to null.
- If date is missing, set date_str to null.
- For "today", keep date_str as "today".
- For "tomorrow", keep date_str as "tomorrow".
- For active/all locations, intent must be get_locations.
- For random/general chatbot questions, intent must be general_chat.

Return exactly this JSON shape:
{
  "intent": "...",
  "model_name": null,
  "location_name": null,
  "date_str": null,
  "raw_query": "..."
}
"""

        user_prompt = f"Query: {user_query}\n\nReturn only JSON."

        try:
            client = await get_llm_client()

            response = await client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {
                        "role": "system",
                        "content": system_prompt
                    },
                    {
                        "role": "user",
                        "content": user_prompt
                    }
                ],
                response_format={
                    "type": "json_object"
                },
                temperature=0.0,
                max_tokens=400
            )

            content = response.choices[0].message.content.strip()
            parsed = json.loads(content)

            parsed["raw_query"] = user_query

            return QueryIntent.model_validate(parsed)

        except Exception as e:
            print(f"[QueryParser] Error parsing: {e}")
            return self._keyword_fallback(user_query)

    async def generate_general_answer(
        self,
        user_query: str,
        context: Optional[dict] = None
    ) -> str:
        """
        General chatbot fallback using Groq.

        This is used when:
        - query is general_chat
        - query is unknown
        - backend API cannot answer
        - random user question should still get a helpful answer
        """

        context = context or {}

        system_prompt = """
You are the BykeMania AI Operations Assistant.

You help different departments such as:
- Service Department
- Fleet Department
- Recovery Department
- Compliance Department
- Operations team

You can answer general operational questions, explain dashboard terms,
explain alert meanings, guide users on what to check, and help them
understand fleet operations.

Rules:
- Be helpful and practical.
- Do not invent live fleet numbers.
- If live data is needed, say that the dashboard or alert APIs should be checked.
- If the user asks for private backend details, do not reveal secrets.
- Keep answers concise and useful.
"""

        user_prompt = f"""
User question:
{user_query}

Available context:
{json.dumps(context, ensure_ascii=False, default=str)}

Answer clearly.
"""

        try:
            client = await get_llm_client()

            response = await client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {
                        "role": "system",
                        "content": system_prompt
                    },
                    {
                        "role": "user",
                        "content": user_prompt
                    }
                ],
                temperature=0.3,
                max_tokens=600
            )

            return response.choices[0].message.content.strip()

        except Exception as e:
            print(f"[GeneralAnswer] Error: {e}")

            return (
                "I can help with fleet availability, locations, models, alerts, "
                "department-wise operations, and dashboard explanations. "
                "Ask me something like: 'show Activa at Koramangala today', "
                "'list active locations', or 'explain service alerts'."
            )


if __name__ == "__main__":
    import asyncio

    async def test():
        parser = QueryParser()

        queries = [
            "total Activa at Koramangala today",
            "Tell me all the active locations",
            "What does force block mean?",
            "hello"
        ]

        for query in queries:
            result = await parser.parse(query)
            print(result.model_dump_json(indent=2))

    asyncio.run(test())
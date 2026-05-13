# app/services/query_parser.py
from pydantic import BaseModel, Field
from typing import Optional, Literal
import json

from ..llm.router import get_llm_client


class QueryIntent(BaseModel):
    intent: Literal[
        "get_availability", 
        "get_models_at_location", 
        "get_utilization", 
        "get_all_models",
        "unknown"
    ] = Field(..., description="Main intent of the query")
    
    model_name: Optional[str] = Field(None, description="Bike/scooter model name e.g. Activa, Access, Jupiter, KTM")
    location_name: Optional[str] = Field(None, description="Location name e.g. Koramangala, Indiranagar, HSR Layout")
    date_str: Optional[str] = Field(None, description="Date - keep as 'today', 'tomorrow', 'next week' or YYYY-MM-DD")
    raw_query: str = Field(..., description="Original user query")


class QueryParser:
    async def parse(self, user_query: str) -> QueryIntent:
        client = await get_llm_client()
        
        system_prompt = """
You are a precise query parser for BykeMania Ops team.

Return ONLY a valid JSON object with exactly these field names:
- intent: one of ["get_availability", "get_models_at_location", "get_utilization", "get_all_models", "unknown"]
- model_name: string or null
- location_name: string or null
- date_str: string or null
- raw_query: the original query string

Rules:
- Use exact field names above. Do not use "model", "location", "date" etc.
- If information is missing, use null.
- Common models: Activa, Access, Jupiter, KTM, Apache, Fascino
- Common locations: Koramangala, Indiranagar, HSR Layout, BTM, Whitefield, Jayanagar
"""

        user_prompt = f"Query: {user_query}\n\nReturn only JSON, no explanation."

        try:
            response = await client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.0,
                max_tokens=400
            )

            content = response.choices[0].message.content.strip()
            parsed = json.loads(content)
            
            # Force raw_query
            parsed["raw_query"] = user_query
            
            query_intent = QueryIntent.model_validate(parsed)
            return query_intent

        except Exception as e:
            print(f"[QueryParser] Error parsing: {e}")
            print(f"Raw LLM output was: {content if 'content' in locals() else 'N/A'}")
            return QueryIntent(
                intent="unknown",
                raw_query=user_query
            )


# Test
if __name__ == "__main__":
    import asyncio
    async def test():
        parser = QueryParser()
        result = await parser.parse("Show Activa availability at Koramangala today")
        print(result.model_dump_json(indent=2))
    
    asyncio.run(test())
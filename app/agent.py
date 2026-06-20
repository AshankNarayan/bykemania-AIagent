from datetime import datetime, timezone
from uuid import uuid4

from app.tools.optimized_api import call_sir_optimized_api_with_metadata
from app.services.response_formatter import ResponseFormatter
from app.services.query_parser import QueryParser
from app.storage.log_repository import AgentLogRepository


class BykeManiaAgent:
    def __init__(self):
        self.formatter = ResponseFormatter()
        self.parser = QueryParser()
        self.log_repo = AgentLogRepository()

    async def process_query(self, user_query: str) -> dict:
        """
        Main agent flow:
        1. Save initial query log
        2. Parse user query using LLM
        3. Call optimized PHP API
        4. Format response
        5. Save raw API response + final formatted response with timestamp
        """

        request_id = str(uuid4())

        self.log_repo.create_started_log(
            request_id=request_id,
            user_query=user_query
        )

        print(f"🔍 Processing query: {user_query}")
        print(f"🆔 Request ID: {request_id}")

        try:
            # Step 1: Parse natural language query
            query_intent = await self.parser.parse(user_query)
            parsed_intent = query_intent.model_dump()

            print(f"🧠 Parsed intent: {parsed_intent}")

            self.log_repo.update_after_parse(
                request_id=request_id,
                parsed_intent=parsed_intent
            )

            # Step 2: Call Sir's optimized API with metadata
            api_result = await call_sir_optimized_api_with_metadata(
                location=query_intent.location_name,
                date=query_intent.date_str
            )

            self.log_repo.update_after_api(
                request_id=request_id,
                api_result=api_result
            )

            # Step 3: Handle API failure
            if not api_result.get("success"):
                response_data = {
                    "summary": "❌ Backend API is not responding correctly right now.",
                    "total_records": 0,
                    "filters": {
                        "location": query_intent.location_name,
                        "model": query_intent.model_name,
                        "date": query_intent.date_str
                    },
                    "data": [],
                    "request_id": request_id,
                    "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                    "error": api_result.get("error")
                }

                self.log_repo.finish_error(
                    request_id=request_id,
                    error_message=api_result.get("error") or "API call failed",
                    formatted_response=response_data
                )

                return response_data

            api_data = api_result.get("data", [])

            if not api_data:
                response_data = {
                    "summary": "No data found from API.",
                    "total_records": 0,
                    "filters": {
                        "location": query_intent.location_name,
                        "model": query_intent.model_name,
                        "date": query_intent.date_str
                    },
                    "data": [],
                    "request_id": request_id,
                    "timestamp_utc": datetime.now(timezone.utc).isoformat()
                }

                self.log_repo.finish_success(
                    request_id=request_id,
                    formatted_response=response_data
                )

                return response_data

            # Step 4: Format clean response
            response_data = self.formatter.format_availability_response(
                query_intent,
                api_data
            )

            # Add tracking metadata to final response
            response_data["request_id"] = request_id
            response_data["timestamp_utc"] = datetime.now(timezone.utc).isoformat()

            # Step 5: Save final formatted response
            self.log_repo.finish_success(
                request_id=request_id,
                formatted_response=response_data
            )

            return response_data

        except Exception as e:
            error_message = f"{type(e).__name__}: {str(e)}"
            print(f"[Agent Error] {error_message}")

            response_data = {
                "summary": "❌ Sorry, something went wrong while processing your query.",
                "total_records": 0,
                "data": [],
                "request_id": request_id,
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                "error": error_message
            }

            self.log_repo.finish_error(
                request_id=request_id,
                error_message=error_message,
                formatted_response=response_data
            )

            return response_data
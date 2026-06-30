from datetime import datetime, timezone
from typing import Any, Dict, List
from uuid import uuid4

from app.tools.optimized_api import call_sir_optimized_api_with_metadata
from app.services.response_formatter import ResponseFormatter
from app.services.query_parser import QueryParser, QueryIntent
from app.storage.log_repository import AgentLogRepository


class BykeManiaAgent:
    """
    Main AI agent.

    New behavior:
    - Known fleet query: calls backend API
    - Active locations query: calls backend API and extracts locations
    - General query: answers using Groq fallback
    - Logging failure never crashes /chat
    - Parser/API failure returns graceful response
    """

    def __init__(self):
        self.formatter = ResponseFormatter()
        self.parser = QueryParser()
        self.log_repo = AgentLogRepository()

    def _now_utc(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _safe_log(self, method_name: str, **kwargs) -> None:
        """
        Logging should never break /chat.

        If logging fails, we print the error and continue.
        """

        try:
            method = getattr(self.log_repo, method_name, None)

            if not method:
                print(f"[Log Warning] Missing log method: {method_name}")
                return

            method(**kwargs)

        except Exception as e:
            print(f"[Log Warning] {method_name} failed: {type(e).__name__}: {e}")

    def _safe_text(self, value: Any) -> str:
        if value is None:
            return ""

        return str(value).strip()

    def _is_inactive_location(self, location_name: str) -> bool:
        location = location_name.lower().strip()

        inactive_keywords = [
            "sold",
            "missing",
            "scrap",
            "inactive"
        ]

        return any(keyword in location for keyword in inactive_keywords)

    def _get_location_from_record(self, record: Dict[str, Any]) -> str:
        possible_keys = [
            "location_name",
            "Location",
            "location",
            "branch",
            "station"
        ]

        for key in possible_keys:
            value = self._safe_text(record.get(key))

            if value:
                return value

        return ""

    def _get_model_from_record(self, record: Dict[str, Any]) -> str:
        possible_keys = [
            "bike_type",
            "model_name",
            "model",
            "vehicle_model",
            "bike_model"
        ]

        for key in possible_keys:
            value = self._safe_text(record.get(key))

            if value:
                return value

        return ""

    def _format_locations_response(
        self,
        api_data: List[Dict[str, Any]],
        request_id: str
    ) -> Dict[str, Any]:
        """
        Builds active location response from backend API data.
        """

        location_count: Dict[str, int] = {}

        for record in api_data:
            location_name = self._get_location_from_record(record)

            if not location_name:
                continue

            if self._is_inactive_location(location_name):
                continue

            location_count[location_name] = location_count.get(location_name, 0) + 1

        locations = [
            {
                "location_name": location,
                "vehicle_count": count
            }
            for location, count in sorted(
                location_count.items(),
                key=lambda item: item[0].lower()
            )
        ]

        return {
            "answer_type": "locations",
            "summary": (
                f"Found {len(locations)} active locations."
                if locations
                else "No active locations found from the current backend data."
            ),
            "total_locations": len(locations),
            "total_records_checked": len(api_data),
            "locations": locations,
            "request_id": request_id,
            "timestamp_utc": self._now_utc()
        }

    def _format_models_response(
        self,
        api_data: List[Dict[str, Any]],
        request_id: str
    ) -> Dict[str, Any]:
        """
        Builds model list response from backend API data.
        """

        model_count: Dict[str, int] = {}

        for record in api_data:
            model_name = self._get_model_from_record(record)

            if not model_name:
                continue

            model_count[model_name] = model_count.get(model_name, 0) + 1

        models = [
            {
                "model_name": model,
                "vehicle_count": count
            }
            for model, count in sorted(
                model_count.items(),
                key=lambda item: item[0].lower()
            )
        ]

        return {
            "answer_type": "models",
            "summary": (
                f"Found {len(models)} vehicle models."
                if models
                else "No vehicle models found from the current backend data."
            ),
            "total_models": len(models),
            "total_records_checked": len(api_data),
            "models": models,
            "request_id": request_id,
            "timestamp_utc": self._now_utc()
        }

    async def _general_chat_response(
        self,
        user_query: str,
        query_intent: QueryIntent,
        request_id: str,
        extra_context: Dict[str, Any] | None = None
    ) -> Dict[str, Any]:
        """
        Uses Groq to answer general chatbot questions.
        """

        context = {
            "parsed_intent": query_intent.model_dump()
        }

        if extra_context:
            context.update(extra_context)

        answer = await self.parser.generate_general_answer(
            user_query=user_query,
            context=context
        )

        return {
            "answer_type": "general_chat",
            "summary": answer,
            "total_records": 0,
            "filters": {
                "location": query_intent.location_name,
                "model": query_intent.model_name,
                "date": query_intent.date_str
            },
            "data": [],
            "request_id": request_id,
            "timestamp_utc": self._now_utc()
        }

    async def process_query(self, user_query: str) -> dict:
        """
        Main agent flow.

        It always tries to return a useful response.
        """

        request_id = str(uuid4())

        print(f"🔍 Processing query: {user_query}")
        print(f"🆔 Request ID: {request_id}")

        self._safe_log(
            "create_started_log",
            request_id=request_id,
            user_query=user_query
        )

        try:
            query_intent = await self.parser.parse(user_query)
            parsed_intent = query_intent.model_dump()

            print(f"🧠 Parsed intent: {parsed_intent}")

            self._safe_log(
                "update_after_parse",
                request_id=request_id,
                parsed_query=parsed_intent
            )

            if query_intent.intent in ["general_chat", "unknown"]:
                response_data = await self._general_chat_response(
                    user_query=user_query,
                    query_intent=query_intent,
                    request_id=request_id
                )

                self._safe_log(
                    "finish_success",
                    request_id=request_id,
                    formatted_response=response_data
                )

                return response_data

            api_result = await call_sir_optimized_api_with_metadata(
                location=query_intent.location_name,
                date=query_intent.date_str
            )

            self._safe_log(
                "update_after_api",
                request_id=request_id,
                api_result=api_result
            )

            if not api_result.get("success"):
                fallback_answer = await self.parser.generate_general_answer(
                    user_query=user_query,
                    context={
                        "parsed_intent": parsed_intent,
                        "backend_error": api_result.get("error")
                    }
                )

                response_data = {
                    "answer_type": "backend_error_with_chat_fallback",
                    "summary": (
                        "The live backend data could not be reached right now. "
                        + fallback_answer
                    ),
                    "total_records": 0,
                    "filters": {
                        "location": query_intent.location_name,
                        "model": query_intent.model_name,
                        "date": query_intent.date_str
                    },
                    "data": [],
                    "request_id": request_id,
                    "timestamp_utc": self._now_utc(),
                    "error": api_result.get("error")
                }

                self._safe_log(
                    "finish_error",
                    request_id=request_id,
                    error_message=api_result.get("error") or "API call failed",
                    parsed_query=parsed_intent,
                    api_result=api_result,
                    formatted_response=response_data
                )

                return response_data

            api_data = api_result.get("data", [])

            if not isinstance(api_data, list):
                response_data = {
                    "answer_type": "invalid_backend_data",
                    "summary": "The backend returned data in an unexpected format.",
                    "total_records": 0,
                    "filters": {
                        "location": query_intent.location_name,
                        "model": query_intent.model_name,
                        "date": query_intent.date_str
                    },
                    "data": [],
                    "request_id": request_id,
                    "timestamp_utc": self._now_utc()
                }

                self._safe_log(
                    "finish_error",
                    request_id=request_id,
                    error_message="Backend returned non-list data.",
                    parsed_query=parsed_intent,
                    api_result=api_result,
                    formatted_response=response_data
                )

                return response_data

            if query_intent.intent == "get_locations":
                response_data = self._format_locations_response(
                    api_data=api_data,
                    request_id=request_id
                )

                self._safe_log(
                    "finish_success",
                    request_id=request_id,
                    formatted_response=response_data
                )

                return response_data

            if query_intent.intent == "get_all_models":
                response_data = self._format_models_response(
                    api_data=api_data,
                    request_id=request_id
                )

                self._safe_log(
                    "finish_success",
                    request_id=request_id,
                    formatted_response=response_data
                )

                return response_data

            if not api_data:
                response_data = {
                    "answer_type": "no_data",
                    "summary": "No matching live fleet data was found for this query.",
                    "total_records": 0,
                    "filters": {
                        "location": query_intent.location_name,
                        "model": query_intent.model_name,
                        "date": query_intent.date_str
                    },
                    "data": [],
                    "request_id": request_id,
                    "timestamp_utc": self._now_utc()
                }

                self._safe_log(
                    "finish_success",
                    request_id=request_id,
                    formatted_response=response_data
                )

                return response_data

            response_data = self.formatter.format_availability_response(
                query_intent,
                api_data
            )

            response_data["answer_type"] = query_intent.intent
            response_data["request_id"] = request_id
            response_data["timestamp_utc"] = self._now_utc()

            self._safe_log(
                "finish_success",
                request_id=request_id,
                formatted_response=response_data
            )

            return response_data

        except Exception as e:
            error_message = f"{type(e).__name__}: {str(e)}"
            print(f"[Agent Error] {error_message}")

            fallback_intent = QueryIntent(
                intent="general_chat",
                model_name=None,
                location_name=None,
                date_str=None,
                raw_query=user_query
            )

            try:
                response_data = await self._general_chat_response(
                    user_query=user_query,
                    query_intent=fallback_intent,
                    request_id=request_id,
                    extra_context={
                        "internal_error": error_message
                    }
                )

                response_data["answer_type"] = "general_chat_after_internal_error"
                response_data["internal_error"] = error_message

            except Exception:
                response_data = {
                    "answer_type": "safe_error",
                    "summary": (
                        "I could not process the live operation request right now, "
                        "but the chat service is still running. Please try a simpler query "
                        "like 'show Activa at Koramangala today' or 'list active locations'."
                    ),
                    "total_records": 0,
                    "data": [],
                    "request_id": request_id,
                    "timestamp_utc": self._now_utc(),
                    "error": error_message
                }

            self._safe_log(
                "finish_error",
                request_id=request_id,
                error_message=error_message,
                formatted_response=response_data
            )

            return response_data
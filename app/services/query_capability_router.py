import asyncio
import json
import os
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class QueryCapability:
    task_type: str = "current_fleet_query"
    requires_historical_data: bool = False
    can_answer_with_current_fleet_only: bool = True
    needs_advanced_analytics: bool = False
    location: Optional[str] = None
    vehicle_model: Optional[str] = None
    time_window: Optional[str] = None
    required_data_sources: List[str] = field(default_factory=list)
    available_data_sources: List[str] = field(default_factory=list)
    missing_data_sources: List[str] = field(default_factory=list)
    should_request_data: bool = False
    confidence: float = 0.0
    reason: str = ""
    router_source: str = "fallback"

    def model_dump(self) -> Dict[str, Any]:
        return asdict(self)


class QueryCapabilityRouter:
    """
    Groq-powered query capability router.

    Purpose:
    - Understand whether a user query is a simple current fleet query
      or an advanced analytics query.
    - Prevent forecasting/revenue/customer queries from being incorrectly
      answered using only current fleet data.
    - Return structured capability JSON before the normal parser runs.
    """

    ADVANCED_TASK_TYPES = {
        "demand_forecast",
        "shortage_prediction",
        "fleet_reallocation",
        "revenue_analysis",
        "customer_analysis",
    }

    SIMPLE_TASK_TYPES = {
        "current_fleet_query",
        "alert_query",
        "executive_summary",
        "general_chat",
        "unknown",
    }

    TASK_REQUIRED_SOURCES = {
        "demand_forecast": [
            "booking_history",
            "availability_snapshots",
            "current_fleet",
        ],
        "shortage_prediction": [
            "booking_history",
            "availability_snapshots",
            "current_fleet",
        ],
        "fleet_reallocation": [
            "booking_history",
            "availability_snapshots",
            "current_fleet",
        ],
        "revenue_analysis": [
            "revenue_data",
        ],
        "customer_analysis": [
            "customer_feedback",
        ],
    }

    TASK_ALIASES = {
        "availability": "current_fleet_query",
        "fleet_status": "current_fleet_query",
        "current_availability": "current_fleet_query",
        "fleet_query": "current_fleet_query",
        "alerts": "alert_query",
        "service_alert": "alert_query",
        "compliance_alert": "alert_query",
        "recovery_alert": "alert_query",
        "forecast": "demand_forecast",
        "prediction": "demand_forecast",
        "demand_prediction": "demand_forecast",
        "stock_prediction": "demand_forecast",
        "stock_forecast": "demand_forecast",
        "shortage": "shortage_prediction",
        "vehicle_shortage": "shortage_prediction",
        "allocation": "fleet_reallocation",
        "fleet_allocation": "fleet_reallocation",
        "reallocation": "fleet_reallocation",
        "revenue": "revenue_analysis",
        "profit": "revenue_analysis",
        "customer": "customer_analysis",
        "complaint": "customer_analysis",
    }

    def __init__(self):
        self.groq_api_key = os.getenv("GROQ_API_KEY", "").strip()
        self.groq_model = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant").strip()
        self.groq_url = "https://api.groq.com/openai/v1/chat/completions"
        self.timeout_seconds = int(os.getenv("GROQ_ROUTER_TIMEOUT_SECONDS", "15"))

        implemented_raw = os.getenv("IMPLEMENTED_ADVANCED_TASKS", "").strip()

        self.implemented_advanced_tasks = {
            item.strip()
            for item in implemented_raw.split(",")
            if item.strip()
        }

    def _get_available_data_sources(self) -> Dict[str, bool]:
        return {
            "current_fleet": bool(os.getenv("SIR_API_URL", "").strip()),
            "operational_alerts": True,
            "booking_history": bool(os.getenv("BOOKING_HISTORY_API_URL", "").strip()),
            "availability_snapshots": bool(
                os.getenv("AVAILABILITY_SNAPSHOT_API_URL", "").strip()
            ),
            "revenue_data": bool(os.getenv("REVENUE_API_URL", "").strip()),
            "customer_feedback": bool(os.getenv("CUSTOMER_FEEDBACK_API_URL", "").strip()),
        }

    def _normalize_task_type(self, task_type: Any) -> str:
        raw = str(task_type or "unknown").strip().lower()

        if raw in self.TASK_ALIASES:
            return self.TASK_ALIASES[raw]

        if raw in self.ADVANCED_TASK_TYPES or raw in self.SIMPLE_TASK_TYPES:
            return raw

        return "unknown"

    def _safe_bool(self, value: Any, default: bool = False) -> bool:
        if isinstance(value, bool):
            return value

        if isinstance(value, str):
            lowered = value.strip().lower()

            if lowered in ["true", "yes", "1"]:
                return True

            if lowered in ["false", "no", "0"]:
                return False

        return default

    def _safe_float(self, value: Any, default: float = 0.0) -> float:
        try:
            number = float(value)
            return max(0.0, min(1.0, number))
        except Exception:
            return default

    def _extract_json_from_text(self, text: str) -> Dict[str, Any]:
        cleaned = text.strip()

        try:
            return json.loads(cleaned)
        except Exception:
            pass

        start = cleaned.find("{")
        end = cleaned.rfind("}")

        if start != -1 and end != -1 and end > start:
            possible_json = cleaned[start:end + 1]

            try:
                return json.loads(possible_json)
            except Exception:
                return {}

        return {}

    def _build_prompt(self, user_query: str) -> List[Dict[str, str]]:
        system_prompt = """
You are a query capability classifier for the BykeMania operations AI assistant.

Your job is NOT to answer the user's question.
Your job is only to classify what kind of data/tooling is required.

Allowed task_type values:
1. current_fleet_query
   - Current/today vehicle count, availability, active locations, model count.
   - Example: "How many Activa are available at Koramangala today?"

2. alert_query
   - Service alerts, compliance alerts, recovery alerts, blocked vehicles.
   - Example: "Show all service alerts."

3. demand_forecast
   - Predicting demand, required stock, expected bookings, high/low demand.
   - Examples:
     "Predict required Activa stock tomorrow morning."
     "Which bike model will be in high demand this weekend?"
     "According to demand trend, what vehicles should be available tomorrow?"

4. shortage_prediction
   - Predicting which location/model may face shortage in the future.
   - Example:
     "Which location may face vehicle shortage tomorrow?"

5. fleet_reallocation
   - Moving/shifting/reallocating vehicles between locations.
   - Example:
     "Which vehicles should be shifted from Koramangala to Indiranagar?"

6. revenue_analysis
   - Revenue, profit, income, payment, earnings, best earning model/location.
   - Example:
     "Which location generated highest revenue last week?"

7. customer_analysis
   - Customer complaint, rating, feedback, satisfaction, churn, repeated complaints.
   - Example:
     "Which location has highest customer complaints?"

8. executive_summary
   - Today's operational risks, CEO-style summary, what team should focus on.
   - Example:
     "What should the operations team focus on today?"

9. general_chat
   - Greetings, project explanation, general assistant questions.

Classification rules:
- If the query asks to predict, forecast, estimate, expect, likely, required stock,
  demand trend, shortage tomorrow, high demand, low demand, weekend demand,
  future allocation, or future availability requirement, classify it as demand_forecast,
  shortage_prediction, or fleet_reallocation.
- Current fleet data alone CANNOT answer true forecast, shortage prediction, revenue,
  customer complaints, or optimal reallocation.
- Do not hallucinate. Do not answer the business question.
- Return JSON only.

Return this JSON shape:
{
  "task_type": "one_allowed_task_type",
  "requires_historical_data": true_or_false,
  "can_answer_with_current_fleet_only": true_or_false,
  "needs_advanced_analytics": true_or_false,
  "location": "location_or_null",
  "vehicle_model": "vehicle_model_or_null",
  "time_window": "time_window_or_null",
  "required_data_sources": ["source_name"],
  "reason": "short reason",
  "confidence": 0.0
}
"""

        return [
            {
                "role": "system",
                "content": system_prompt,
            },
            {
                "role": "user",
                "content": user_query,
            },
        ]

    def _call_groq_sync(self, user_query: str, use_json_mode: bool = True) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "model": self.groq_model,
            "messages": self._build_prompt(user_query),
            "temperature": 0,
            "max_tokens": 700,
        }

        if use_json_mode:
            payload["response_format"] = {"type": "json_object"}

        body = json.dumps(payload).encode("utf-8")

        request = urllib.request.Request(
            self.groq_url,
            data=body,
            method="POST",
            headers={
                "Authorization": f"Bearer {self.groq_api_key}",
                "Content-Type": "application/json",
            },
        )

        with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
            response_body = response.read().decode("utf-8")

        response_json = json.loads(response_body)
        content = (
            response_json
            .get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
        )

        return self._extract_json_from_text(content)

    async def _call_groq(self, user_query: str) -> Dict[str, Any]:
        if not self.groq_api_key:
            return {}

        try:
            return await asyncio.to_thread(
                self._call_groq_sync,
                user_query,
                True,
            )
        except urllib.error.HTTPError:
            try:
                return await asyncio.to_thread(
                    self._call_groq_sync,
                    user_query,
                    False,
                )
            except Exception as e:
                print(f"[Capability Router] Groq retry failed: {type(e).__name__}: {e}")
                return {}
        except Exception as e:
            print(f"[Capability Router] Groq failed: {type(e).__name__}: {e}")
            return {}

    def _keyword_fallback(self, user_query: str) -> Dict[str, Any]:
        query = user_query.lower().strip()

        revenue_keywords = [
            "revenue",
            "profit",
            "earning",
            "income",
            "payment",
            "amount paid",
            "financial",
            "sales",
            "booking income",
            "best revenue",
            "highest revenue",
        ]

        customer_keywords = [
            "customer complaint",
            "complaint",
            "feedback",
            "rating",
            "nps",
            "customer satisfaction",
            "churn",
            "repeat customer",
            "unhappy",
        ]

        shortage_keywords = [
            "shortage",
            "may face shortage",
            "vehicle shortage",
            "stockout",
            "not enough vehicles",
            "low stock",
            "insufficient stock",
        ]

        reallocation_keywords = [
            "reallocation",
            "reallocate",
            "shift vehicles",
            "move vehicles",
            "transfer vehicles",
            "allocate vehicles",
            "fleet allocation",
            "overstocked",
            "understocked",
            "excess vehicles",
        ]

        forecast_keywords = [
            "predict",
            "forecast",
            "expected",
            "likely",
            "demand trend",
            "booking trend",
            "rental trend",
            "required stock",
            "required activa stock",
            "required vehicles",
            "should be available",
            "high demand",
            "low demand",
            "tomorrow morning",
            "this weekend",
            "next week",
        ]

        alert_keywords = [
            "alert",
            "service",
            "compliance",
            "recovery",
            "blocked",
            "force block",
            "insurance",
            "document",
        ]

        executive_keywords = [
            "operations summary",
            "operational summary",
            "biggest operational risks",
            "what should the operations team focus",
            "ceo-style",
            "focus today",
            "immediate attention",
        ]

        if any(keyword in query for keyword in revenue_keywords):
            return {
                "task_type": "revenue_analysis",
                "requires_historical_data": True,
                "can_answer_with_current_fleet_only": False,
                "needs_advanced_analytics": True,
                "required_data_sources": ["revenue_data"],
                "reason": "The query asks for revenue or financial analysis.",
                "confidence": 0.85,
            }

        if any(keyword in query for keyword in customer_keywords):
            return {
                "task_type": "customer_analysis",
                "requires_historical_data": True,
                "can_answer_with_current_fleet_only": False,
                "needs_advanced_analytics": True,
                "required_data_sources": ["customer_feedback"],
                "reason": "The query asks for customer feedback or complaint analysis.",
                "confidence": 0.85,
            }

        if any(keyword in query for keyword in shortage_keywords):
            return {
                "task_type": "shortage_prediction",
                "requires_historical_data": True,
                "can_answer_with_current_fleet_only": False,
                "needs_advanced_analytics": True,
                "required_data_sources": [
                    "booking_history",
                    "availability_snapshots",
                    "current_fleet",
                ],
                "reason": "The query asks for future shortage prediction.",
                "confidence": 0.9,
            }

        if any(keyword in query for keyword in reallocation_keywords):
            return {
                "task_type": "fleet_reallocation",
                "requires_historical_data": True,
                "can_answer_with_current_fleet_only": False,
                "needs_advanced_analytics": True,
                "required_data_sources": [
                    "booking_history",
                    "availability_snapshots",
                    "current_fleet",
                ],
                "reason": "The query asks for fleet movement or reallocation recommendation.",
                "confidence": 0.9,
            }

        if any(keyword in query for keyword in forecast_keywords):
            return {
                "task_type": "demand_forecast",
                "requires_historical_data": True,
                "can_answer_with_current_fleet_only": False,
                "needs_advanced_analytics": True,
                "required_data_sources": [
                    "booking_history",
                    "availability_snapshots",
                    "current_fleet",
                ],
                "reason": "The query asks for prediction, future demand, or required stock.",
                "confidence": 0.88,
            }

        if any(keyword in query for keyword in executive_keywords):
            return {
                "task_type": "executive_summary",
                "requires_historical_data": False,
                "can_answer_with_current_fleet_only": False,
                "needs_advanced_analytics": False,
                "required_data_sources": ["current_fleet", "operational_alerts"],
                "reason": "The query asks for an operations summary.",
                "confidence": 0.75,
            }

        if any(keyword in query for keyword in alert_keywords):
            return {
                "task_type": "alert_query",
                "requires_historical_data": False,
                "can_answer_with_current_fleet_only": False,
                "needs_advanced_analytics": False,
                "required_data_sources": ["operational_alerts", "current_fleet"],
                "reason": "The query asks about operational alerts.",
                "confidence": 0.75,
            }

        return {
            "task_type": "current_fleet_query",
            "requires_historical_data": False,
            "can_answer_with_current_fleet_only": True,
            "needs_advanced_analytics": False,
            "required_data_sources": ["current_fleet"],
            "reason": "Fallback classified this as a current fleet query.",
            "confidence": 0.5,
        }

    def _finalize_capability(
        self,
        raw_capability: Dict[str, Any],
        router_source: str,
    ) -> QueryCapability:
        task_type = self._normalize_task_type(raw_capability.get("task_type"))

        required_sources = raw_capability.get("required_data_sources") or []

        if not isinstance(required_sources, list):
            required_sources = []

        if task_type in self.TASK_REQUIRED_SOURCES:
            required_sources = list(
                dict.fromkeys(
                    required_sources + self.TASK_REQUIRED_SOURCES[task_type]
                )
            )

        source_status = self._get_available_data_sources()

        available_sources = [
            source for source in required_sources
            if source_status.get(source, False)
        ]

        missing_sources = [
            source for source in required_sources
            if not source_status.get(source, False)
        ]

        requires_historical_data = self._safe_bool(
            raw_capability.get("requires_historical_data"),
            task_type in self.ADVANCED_TASK_TYPES,
        )

        can_answer_with_current_fleet_only = self._safe_bool(
            raw_capability.get("can_answer_with_current_fleet_only"),
            task_type == "current_fleet_query",
        )

        needs_advanced_analytics = self._safe_bool(
            raw_capability.get("needs_advanced_analytics"),
            task_type in self.ADVANCED_TASK_TYPES,
        )

        advanced_task_not_implemented = (
            task_type in self.ADVANCED_TASK_TYPES
            and task_type not in self.implemented_advanced_tasks
        )

        should_request_data = (
            task_type in self.ADVANCED_TASK_TYPES
            and (
                bool(missing_sources)
                or requires_historical_data
                or needs_advanced_analytics
                or not can_answer_with_current_fleet_only
                or advanced_task_not_implemented
            )
        )

        return QueryCapability(
            task_type=task_type,
            requires_historical_data=requires_historical_data,
            can_answer_with_current_fleet_only=can_answer_with_current_fleet_only,
            needs_advanced_analytics=needs_advanced_analytics,
            location=raw_capability.get("location"),
            vehicle_model=raw_capability.get("vehicle_model"),
            time_window=raw_capability.get("time_window"),
            required_data_sources=required_sources,
            available_data_sources=available_sources,
            missing_data_sources=missing_sources,
            should_request_data=should_request_data,
            confidence=self._safe_float(raw_capability.get("confidence"), 0.0),
            reason=str(raw_capability.get("reason") or "").strip(),
            router_source=router_source,
        )

    async def classify(self, user_query: str) -> Dict[str, Any]:
        groq_result = await self._call_groq(user_query)

        if groq_result:
            capability = self._finalize_capability(
                raw_capability=groq_result,
                router_source="groq",
            )

            return capability.model_dump()

        fallback_result = self._keyword_fallback(user_query)

        capability = self._finalize_capability(
            raw_capability=fallback_result,
            router_source="keyword_fallback",
        )

        return capability.model_dump()
# app/services/response_formatter.py
from typing import Dict, Any, List
from datetime import datetime


class ResponseFormatter:
    @staticmethod
    def format_utilization(util_str: str) -> Dict[str, Any]:
        if not util_str or util_str.lower() == "null":
            return {"available": 0, "live_booking": 0, "blocked": 0, "recovery": 0, "status": "NA"}
        parts = util_str.split("|")
        try:
            return {
                "available": int(parts[0]) if len(parts) > 0 else 0,
                "live_booking": int(parts[1]) if len(parts) > 1 else 0,
                "blocked": int(parts[2]) if len(parts) > 2 else 0,
                "recovery": int(parts[3]) if len(parts) > 3 else 0,
                "status": parts[4] if len(parts) > 4 else "NA"
            }
        except:
            return {"available": 0, "live_booking": 0, "blocked": 0, "recovery": 0, "status": "NA"}

    @staticmethod
    def format_availability_response(query_intent: Any, api_data: List[Dict]) -> str:
        """FINAL ROBUST VERSION - Handles your exact PHP API structure"""
        print(f"DEBUG: Received {len(api_data) if isinstance(api_data, list) else 1} top-level records")

        # Handle different possible structures from the API
        if isinstance(api_data, dict) and "data" in api_data:
            api_data = api_data["data"]  # unwrap "data" key

        if not api_data or not isinstance(api_data, list) or len(api_data) == 0:
            return "No data found from API."

        record = api_data[0]
        print(f"DEBUG: Record keys: {list(record.keys())}")

        models_data = record.get("models", {})
        print(f"DEBUG: Found {len(models_data)} models in 'models' key")

        if not models_data:
            return "No model data available in the API response."

        output = []
        output.append(f"FLEET STATUS - {datetime.now().strftime('%d %b %Y')}")
        output.append("=" * 65)
        
        if query_intent.model_name:
            output.append(f"Model     : {query_intent.model_name}")
        if query_intent.location_name:
            output.append(f"Location  : {query_intent.location_name}")
        if query_intent.date_str:
            output.append(f"Date      : {query_intent.date_str}")
        
        output.append("\nMODEL          AVAIL   LIVE   BLOCK   RECOV   TOTAL")
        output.append("-" * 65)

        for model_key, model_info in models_data.items():
            model_name = query_intent.model_name or model_key
            raw_util = model_info.get("raw", "0|0|0|0|0")
            util = ResponseFormatter.format_utilization(raw_util)
            total = util["available"] + util["live_booking"] + util["blocked"] + util["recovery"]
            
            output.append(
                f"{model_name:<14} {util['available']:>5}   {util['live_booking']:>4}   "
                f"{util['blocked']:>5}   {util['recovery']:>5}   {total:>5}"
            )

        output.append("\n✅ Query processed successfully.")
        return "\n".join(output)


# Quick test
if __name__ == "__main__":
    from app.services.query_parser import QueryIntent
    formatter = ResponseFormatter()
    sample = [{"models": {"model_11": {"raw": "4|3|1|1|0"}}}]
    query = QueryIntent(intent="get_models_at_location", model_name=None, location_name="Koramangala", date_str="today", raw_query="")
    print(formatter.format_availability_response(query, sample))
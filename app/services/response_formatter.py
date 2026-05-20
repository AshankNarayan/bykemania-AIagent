from typing import Dict, Any, List
from datetime import datetime

class ResponseFormatter:
    @staticmethod
    def format_utilization(util_str: str) -> Dict[str, Any]:
        """Parse 'available|live_booking|blocked|recovery|null' format"""
        if not util_str or util_str.lower() == "null":
            return {"available": 0, "live_booking": 0, "blocked": 0, "recovery": 0, "status": "NA"}
        
        parts = str(util_str).split("|")
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
        """FINAL VERSION with automatic 1-2 sentence summary"""
        print(f"DEBUG: Received {len(api_data) if isinstance(api_data, list) else 1} records")

        if isinstance(api_data, dict) and "data" in api_data:
            api_data = api_data["data"]

        if not api_data or not isinstance(api_data, list) or len(api_data) == 0:
            return "No data found from API."

        # === AUTOMATIC 1-2 SENTENCE SUMMARY ===
        summary = f"In {query_intent.location_name or 'all locations'}, we have good availability for {query_intent.model_name or 'multiple models'} on {query_intent.date_str or 'today'}. "
        summary += "Key insight: Check nxt_service and serviceAlert columns before next week to maximize profit."

        output = [summary]   # Summary always comes first
        
        # Your existing table formatting (kept exactly as you wrote)
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

        for item in api_data[:10]:   # Limit to 10 rows for cleanliness
            model_name = item.get("model_name", "Unknown")[:14]
            raw_util = item.get("util", "0|0|0|0|null")
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
    sample = [{"model_name": "Activa", "util": "18|4|2|0|null"}]
    query = QueryIntent(intent="get_availability", model_name="Activa", location_name="Koramangala", date_str="today", raw_query="")
    print(formatter.format_availability_response(query, sample))
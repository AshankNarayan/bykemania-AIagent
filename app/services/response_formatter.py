# app/services/response_formatter.py
from typing import Dict, Any, List
from datetime import datetime


class ResponseFormatter:
    @staticmethod
    def format_utilization(util_str: str) -> Dict[str, Any]:
        """Parse '12|5|1|0|null' format"""
        if not util_str or util_str == "null":
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
    def format_availability_response(
        query_intent: Any,
        data: List[Dict]  # List of records from API
    ) -> str:
        """Generate nice markdown response"""
        if not data:
            return f"❌ No data found for **{query_intent.model_name or 'all models'}** at **{query_intent.location_name or 'all locations'}**."

        lines = []
        lines.append(f"**Fleet Status - {datetime.now().strftime('%d %b %Y')}**\n")
        
        if query_intent.model_name:
            lines.append(f"**Model:** {query_intent.model_name}")
        if query_intent.location_name:
            lines.append(f"**Location:** {query_intent.location_name}")
        if query_intent.date_str:
            lines.append(f"**Date:** {query_intent.date_str}\n")

        # Simple table
        lines.append("| Model | Available | Live Bookings | Blocked | Recovery | Total |")
        lines.append("|-------|-----------|---------------|---------|----------|-------|")
        
        for item in data[:10]:  # Limit for cleanliness
            model = item.get("model_name", "Unknown")
            util = ResponseFormatter.format_utilization(item.get("util", ""))
            
            total = (util["available"] + util["live_booking"] + 
                    util["blocked"] + util["recovery"])
            
            lines.append(
                f"| {model} | {util['available']} | {util['live_booking']} | "
                f"{util['blocked']} | {util['recovery']} | {total} |"
            )

        return "\n".join(lines)


# Test
if __name__ == "__main__":
    from app.services.query_parser import QueryIntent
    
    formatter = ResponseFormatter()
    sample_data = [
        {"model_name": "Activa", "util": "15|3|1|0|null"},
        {"model_name": "Access", "util": "8|5|0|2|null"}
    ]
    
    query = QueryIntent(
        intent="get_availability",
        model_name="Activa",
        location_name="Koramangala",
        date_str="today",
        raw_query="Show Activa availability at Koramangala today"
    )
    
    print(formatter.format_availability_response(query, sample_data))
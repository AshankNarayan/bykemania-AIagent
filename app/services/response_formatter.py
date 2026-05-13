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
    def format_availability_response(query_intent: Any, data: List[Dict]) -> str:
        """Super clean & readable format"""
        if not data:
            return "No data found."

        output = []
        output.append(f"FLEET STATUS - {datetime.now().strftime('%d %b %Y')}")
        output.append("=" * 55)
        
        output.append(f"Model     : {query_intent.model_name}")
        output.append(f"Location  : {query_intent.location_name}")
        output.append(f"Date      : {query_intent.date_str}")
        output.append("")

        output.append("MODEL          AVAIL   LIVE   BLOCK   RECOV   TOTAL")
        output.append("-" * 55)

        for item in data:
            model = item.get("model_name", "Unknown")[:14]
            util = ResponseFormatter.format_utilization(item.get("util", ""))
            total = util["available"] + util["live_booking"] + util["blocked"] + util["recovery"]
            
            output.append(
                f"{model:<14} {util['available']:>5}   {util['live_booking']:>4}   "
                f"{util['blocked']:>5}   {util['recovery']:>5}   {total:>5}"
            )

        output.append("\n✅ Query processed successfully.")
        return "\n".join(output)
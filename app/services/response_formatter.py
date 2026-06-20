from typing import List, Dict, Any
from datetime import datetime

class ResponseFormatter:
    @staticmethod
    def format_availability_response(query_intent: Any, api_data: List[Dict]) -> Dict:
        """Clean, professional, and dashboard-ready structured JSON"""
        
        if not api_data or not isinstance(api_data, list):
            return {
                "summary": "No data found from API.",
                "total_records": 0,
                "filters": {
                    "location": query_intent.location_name,
                    "model": query_intent.model_name,
                    "date": query_intent.date_str
                },
                "data": []
            }

        # Filter data based on query
        filtered = api_data
        if query_intent.location_name:
            filtered = [item for item in filtered 
                       if query_intent.location_name.lower() in str(item.get("location_name", "")).lower()]
        if query_intent.model_name:
            filtered = [item for item in filtered 
                       if query_intent.model_name.lower() in str(item.get("bike_type", "")).lower()]

        total = len(filtered)

        # Count useful insights
        service_alerts = sum(1 for item in filtered if str(item.get("serviceAlert", "")).lower() == "on")
        blocked = sum(1 for item in filtered if str(item.get("forceBlock", "")).lower() != "off")

        # Meaningful summary
        summary = f"Found **{total}** bikes"
        if query_intent.model_name:
            summary += f" matching **{query_intent.model_name}**"
        if query_intent.location_name:
            summary += f" in **{query_intent.location_name}**"
        summary += "."
        if service_alerts > 0:
            summary += f" **{service_alerts}** bikes have service alerts."
        if blocked > 0:
            summary += f" **{blocked}** bikes are currently blocked."
        summary += " Review nxt_service and serviceAlert to plan next week's allocation."

        # Select only the most useful columns for operations team
        clean_data = []
        for item in filtered:
            clean_data.append({
                "reg_num": item.get("reg_num"),
                "bike_type": item.get("bike_type"),
                "location_name": item.get("location_name"),
                "Current_km": item.get("Current_km"),
                "nxt_service": item.get("nxt_service"),
                "serviceAlert": item.get("serviceAlert"),
                "forceBlock": item.get("forceBlock"),
                "booking_status": item.get("booking_status"),
                "last_ongoing_booking_pickup": item.get("last_ongoing_booking_pickup")
            })

        return {
            "summary": summary,
            "total_records": total,
            "filters": {
                "location": query_intent.location_name,
                "model": query_intent.model_name,
                "date": query_intent.date_str
            },
            "data": clean_data
        }
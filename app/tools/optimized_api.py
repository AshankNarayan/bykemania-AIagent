import httpx
import os
from typing import List, Dict, Any, Optional

async def call_sir_optimized_api(location: Optional[str] = None, date: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Calls Sir's optimized API (28 columns) - NO API KEY REQUIRED
    """
    url = os.getenv("SIR_API_URL")
    if not url:
        print("❌ Missing SIR_API_URL in .env")
        return []

    params = {}
    if location:
        params["location"] = location
    if date:
        params["date"] = date

    headers = {"Content-Type": "application/json"}

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(url, params=params, headers=headers)
            response.raise_for_status()
            data = response.json()
            print(f"✅ Sir API success - {len(data) if isinstance(data, list) else 1} records")
            return data
    except Exception as e:
        print(f"❌ Sir API Error: {e}")
        return []

# TOOL DEFINITION (this is what the agent will use)
sir_optimized_api_tool = {
    "name": "sir_optimized_api",
    "description": (
        "Use this tool when the user asks about current bike fleet, availability, "
        "service status, location-wise bikes, bookings, or vehicle health. "
        "It returns ALL 28 columns: reg_num, bike_type, location_name, Current_km, "
        "nxt_service, serviceUpdateTime, readingUpdateTime, vehicle_check, forceBlock, "
        "serviceAlert, last_location_change, last_cmpltd_booking_drop, "
        "last_ongoing_booking_pickup, booking_status, booking_drop, booking_num, "
        "chassisNo, engineNo, Insurance, emission, validatedInsurance, "
        "validatedFitness, validatedPermit, blockReason, firstGPS, firstGpsDate, "
        "secondGps, secondGpsDate. "
        "IMPORTANT RULES: "
        "1. After getting the data, ALWAYS filter to ONLY the columns needed for the question. "
        "2. NEVER show all 28 columns unless asked. "
        "3. AFTER filtering the table, ALWAYS write 1-2 short sentences as a SUMMARY at the very top. "
        "   Example: 'In Koramangala, 18 bikes are available but 7 need service soon. "
        "   We should move 4 premium models from HSR to balance stock.'"
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "location": {"type": "string", "description": "Optional: area name like Koramangala"},
            "date": {"type": "string", "description": "Optional: date in YYYY-MM-DD"}
        }
    }
}
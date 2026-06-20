import httpx
import os
from typing import List, Dict, Any, Optional


def _safe_api_url(url: Optional[str]) -> Optional[str]:
    """
    Removes query string from URL before saving logs.
    This prevents accidentally logging tokens if they are present in URL params.
    """
    if not url:
        return None

    return url.split("?")[0]


async def call_sir_optimized_api_with_metadata(
    location: Optional[str] = None,
    date: Optional[str] = None
) -> Dict[str, Any]:
    """
    Calls Sir's optimized API and returns:
    - API success/failure
    - status code
    - safe API URL
    - params
    - raw data
    - error message if any
    """

    url = os.getenv("SIR_API_URL")
    safe_url = _safe_api_url(url)

    print(f"DEBUG: SIR_API_URL from .env = {safe_url}")

    params = {}

    if location:
        params["location"] = location

    if date:
        params["date"] = date

    if not url:
        error_message = "SIR_API_URL is not set in .env file"
        print(f"❌ ERROR: {error_message}")

        return {
            "success": False,
            "api_url": safe_url,
            "params": params,
            "status_code": None,
            "data": [],
            "error": error_message
        }

    headers = {
        "Content-Type": "application/json"
    }

    print(f"DEBUG: Calling Sir API with params: {params}")

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(url, params=params, headers=headers)

            print(f"DEBUG: Status code = {response.status_code}")
            print(f"DEBUG: Response text first 300 chars = {response.text[:300]}...")

            response.raise_for_status()

            data = response.json()

            record_count = len(data) if isinstance(data, list) else 1
            print(f"✅ SUCCESS: Received {record_count} records")

            return {
                "success": True,
                "api_url": safe_url,
                "params": params,
                "status_code": response.status_code,
                "data": data,
                "error": None
            }

    except httpx.HTTPStatusError as e:
        error_message = f"HTTP error: {e.response.status_code}"

        try:
            error_data = e.response.json()
        except Exception:
            error_data = e.response.text

        print(f"❌ API HTTP ERROR: {error_message}")

        return {
            "success": False,
            "api_url": safe_url,
            "params": params,
            "status_code": e.response.status_code,
            "data": error_data,
            "error": error_message
        }

    except Exception as e:
        error_message = f"{type(e).__name__}: {str(e)}"
        print(f"❌ API CALL FAILED: {error_message}")

        return {
            "success": False,
            "api_url": safe_url,
            "params": params,
            "status_code": None,
            "data": [],
            "error": error_message
        }


async def call_sir_optimized_api(
    location: Optional[str] = None,
    date: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Backward-compatible function.
    Existing code that expects only API data can still use this.
    """

    result = await call_sir_optimized_api_with_metadata(
        location=location,
        date=date
    )

    data = result.get("data", [])

    if isinstance(data, list):
        return data

    return []


sir_optimized_api_tool = {
    "name": "sir_optimized_api",
    "description": "Use this for current fleet, availability, service status etc.",
    "parameters": {
        "type": "object",
        "properties": {}
    }
}
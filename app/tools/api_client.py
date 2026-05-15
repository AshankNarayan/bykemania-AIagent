# app/tools/api_client.py
import httpx
import os
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta

class ApiClient:
    def __init__(self):
        self.base_url = os.getenv("BYKEMANIA_API_BASE")
        self.endpoint = os.getenv("MODEL_UTILISATION_ENDPOINT")
        self.timeout = httpx.Timeout(15.0)

    def _convert_date(self, date_str: Optional[str]) -> Optional[str]:
        """Convert 'today', 'tomorrow' to YYYY-MM-DD"""
        if not date_str:
            return None
        date_str = date_str.lower()
        if date_str == "today":
            return datetime.now().strftime("%Y-%m-%d")
        if date_str == "tomorrow":
            return (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        return date_str  # already in correct format

    async def get_model_utilisation(
        self,
        model_id: Optional[int] = None,
        location_id: Optional[int] = None,
        date_str: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        
        if not self.base_url or not self.endpoint:
            print("❌ Missing API config in .env")
            return []

        url = f"{self.base_url.rstrip('/')}{self.endpoint}"
        date_param = self._convert_date(date_str)

        params = {}
        if model_id is not None:    params["model_id"] = model_id
        if location_id is not None: params["location_id"] = location_id
        if date_param:              params["date"] = date_param

        print(f"📡 Calling API → {url}")
        print(f"   Params: {params}")

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url, params=params)
                print(f"   Status Code: {response.status_code}")
                print(f"   Raw Response: {response.text[:1000]}...")

                response.raise_for_status()
                data = response.json()
                return data

        except Exception as e:
            print(f"❌ API Error: {e}")
            return []


# Quick test
if __name__ == "__main__":
    import asyncio
    async def test():
        client = ApiClient()
        data = await client.get_model_utilisation(model_id=11, location_id=1000, date_str="today")
        print("Final data:", data)
    asyncio.run(test())
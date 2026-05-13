# app/tools/api_client.py
import httpx
import os
from typing import List, Dict, Any, Optional

class ApiClient:
    def __init__(self):
        self.base_url = os.getenv("PHP_API_BASE_URL", "http://your-php-backend.com/api")
        self.timeout = httpx.Timeout(10.0)
        # self.headers = {"Authorization": f"Bearer {os.getenv('PHP_API_KEY', '')}"}

    async def get_model_utilisation(
        self,
        model_id: Optional[int] = None,
        location_id: Optional[int] = None,
        date_str: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Call real PHP API or return dummy for now"""
        
        print(f"📡 Calling PHP API: model={model_id}, location={location_id}, date={date_str}")

        # === REAL API CALL (uncomment when you have URL) ===
        # async with httpx.AsyncClient(timeout=self.timeout) as client:
        #     params = {}
        #     if model_id: params["model_id"] = model_id
        #     if location_id: params["location_id"] = location_id
        #     if date_str: params["date"] = date_str
        #     
        #     response = await client.get(f"{self.base_url}/model-utilisation", params=params)
        #     response.raise_for_status()
        #     return response.json()

        # Dummy data (keep until real API is ready)
        return [
            {
                "model_name": "Activa",
                "model_id": model_id or 11,
                "location_name": "Koramangala",
                "util": "18|4|2|0|null",
                "date": date_str or "today"
            },
            {
                "model_name": "Access",
                "model_id": 12,
                "location_name": "Koramangala",
                "util": "9|6|1|1|null",
                "date": date_str or "today"
            }
        ]


# Test
if __name__ == "__main__":
    import asyncio
    async def test():
        client = ApiClient()
        data = await client.get_model_utilisation(11, 1000, "today")
        print(data)
    asyncio.run(test())
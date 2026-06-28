import hmac
import os
from typing import Optional

from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader


API_KEY_HEADER_NAME = "x-api-key"

api_key_header = APIKeyHeader(
    name=API_KEY_HEADER_NAME,
    auto_error=False
)


def get_expected_api_key() -> str:
    """
    Reads the backend API key from environment variables.

    Required .env value:
    APP_API_KEY=your_secret_key
    """

    return os.getenv("APP_API_KEY", "").strip()


async def verify_api_key(
    provided_api_key: Optional[str] = Security(api_key_header)
) -> bool:
    """
    Verifies x-api-key header for protected endpoints.

    Request must include:
    x-api-key: your_secret_key
    """

    expected_api_key = get_expected_api_key()

    if not expected_api_key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Server API key is not configured."
        )

    if not provided_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key"
        )

    is_valid = hmac.compare_digest(
        provided_api_key,
        expected_api_key
    )

    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key"
        )

    return True
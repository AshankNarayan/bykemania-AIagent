import argparse
import os
import sys
from typing import Any, Dict, Optional

import requests
from dotenv import load_dotenv


load_dotenv()


DEFAULT_LOCAL_BASE_URL = "http://127.0.0.1:8000"


class SmokeTestResult:
    def __init__(
        self,
        name: str,
        passed: bool,
        status_code: Optional[int] = None,
        message: str = "",
        response_json: Optional[Dict[str, Any]] = None
    ):
        self.name = name
        self.passed = passed
        self.status_code = status_code
        self.message = message
        self.response_json = response_json or {}


def get_api_key() -> str:
    """
    Reads API key safely from environment.

    Priority:
    1. SMOKE_TEST_API_KEY
    2. APP_API_KEY
    """

    return (
        os.getenv("SMOKE_TEST_API_KEY")
        or os.getenv("APP_API_KEY")
        or ""
    ).strip()


def get_base_url(cli_base_url: Optional[str]) -> str:
    """
    Reads base URL safely.

    Priority:
    1. CLI --base-url
    2. SMOKE_TEST_BASE_URL
    3. localhost
    """

    base_url = (
        cli_base_url
        or os.getenv("SMOKE_TEST_BASE_URL")
        or DEFAULT_LOCAL_BASE_URL
    ).strip()

    return base_url.rstrip("/")


def print_header(title: str) -> None:
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)


def print_result(result: SmokeTestResult) -> None:
    status = "PASS" if result.passed else "FAIL"
    status_code = result.status_code if result.status_code is not None else "-"

    print(f"[{status}] {result.name} | HTTP {status_code}")

    if result.message:
        print(f"      {result.message}")


def safe_json(response: requests.Response) -> Dict[str, Any]:
    try:
        data = response.json()

        if isinstance(data, dict):
            return data

        return {
            "data": data
        }

    except Exception:
        return {
            "raw_text": response.text[:500]
        }


def request_get(
    name: str,
    url: str,
    headers: Optional[Dict[str, str]] = None,
    expected_status: int = 200,
    timeout: int = 30
) -> SmokeTestResult:
    try:
        response = requests.get(
            url,
            headers=headers or {},
            timeout=timeout
        )

        response_json = safe_json(response)

        passed = response.status_code == expected_status

        return SmokeTestResult(
            name=name,
            passed=passed,
            status_code=response.status_code,
            message=response_json.get("status", "") or response_json.get("message", ""),
            response_json=response_json
        )

    except Exception as exc:
        return SmokeTestResult(
            name=name,
            passed=False,
            message=f"{type(exc).__name__}: {exc}"
        )


def request_post(
    name: str,
    url: str,
    json_body: Dict[str, Any],
    headers: Optional[Dict[str, str]] = None,
    expected_status: int = 200,
    timeout: int = 60
) -> SmokeTestResult:
    try:
        response = requests.post(
            url,
            json=json_body,
            headers=headers or {},
            timeout=timeout
        )

        response_json = safe_json(response)

        passed = response.status_code == expected_status

        message = (
            response_json.get("status", "")
            or response_json.get("message", "")
            or response_json.get("error", {}).get("code", "")
        )

        return SmokeTestResult(
            name=name,
            passed=passed,
            status_code=response.status_code,
            message=message,
            response_json=response_json
        )

    except Exception as exc:
        return SmokeTestResult(
            name=name,
            passed=False,
            message=f"{type(exc).__name__}: {exc}"
        )


def validate_root_response(result: SmokeTestResult) -> SmokeTestResult:
    if not result.passed:
        return result

    data = result.response_json

    required_keys = [
        "message",
        "status",
        "version",
        "environment",
        "timeout_settings",
        "rate_limit_settings"
    ]

    missing_keys = [
        key
        for key in required_keys
        if key not in data
    ]

    if missing_keys:
        result.passed = False
        result.message = f"Missing keys: {missing_keys}"
        return result

    result.message = f"version={data.get('version')} environment={data.get('environment')}"
    return result


def validate_chat_response(result: SmokeTestResult) -> SmokeTestResult:
    if not result.passed:
        return result

    data = result.response_json

    if data.get("status") != "success":
        result.passed = False
        result.message = "Expected status=success"
        return result

    response_data = data.get("response", {})

    if not isinstance(response_data, dict):
        result.passed = False
        result.message = "Missing response object"
        return result

    answer_type = response_data.get("answer_type", "unknown")

    result.message = f"answer_type={answer_type}"
    return result


def validate_scheduler_response(result: SmokeTestResult) -> SmokeTestResult:
    if not result.passed:
        return result

    data = result.response_json

    scheduler = data.get("scheduler", {})

    if not isinstance(scheduler, dict):
        result.passed = False
        result.message = "Missing scheduler object"
        return result

    result.message = f"enabled={scheduler.get('enabled')}"
    return result


def run_smoke_tests(base_url: str, api_key: str) -> int:
    print_header("BykeMania AI Agent Smoke Test")
    print(f"Base URL: {base_url}")

    if not api_key:
        print("\nERROR: Missing API key.")
        print("Set APP_API_KEY in .env or SMOKE_TEST_API_KEY in environment.")
        return 1

    auth_headers = {
        "x-api-key": api_key,
        "Content-Type": "application/json"
    }

    tests: list[SmokeTestResult] = []

    root_result = request_get(
        name="GET /",
        url=f"{base_url}/"
    )
    tests.append(validate_root_response(root_result))

    tests.append(
        request_get(
            name="GET /health",
            url=f"{base_url}/health"
        )
    )

    tests.append(
        request_get(
            name="GET /ready",
            url=f"{base_url}/ready"
        )
    )

    chat_result = request_post(
        name="POST /chat",
        url=f"{base_url}/chat",
        json_body={
            "query": "hello"
        },
        headers=auth_headers,
        timeout=90
    )
    tests.append(validate_chat_response(chat_result))

    tests.append(
        request_get(
            name="GET /logs/recent",
            url=f"{base_url}/logs/recent?limit=3",
            headers=auth_headers
        )
    )

    scheduler_result = request_get(
        name="GET /scheduler/status",
        url=f"{base_url}/scheduler/status",
        headers=auth_headers
    )
    tests.append(validate_scheduler_response(scheduler_result))

    print_header("Results")

    passed_count = 0

    for result in tests:
        print_result(result)

        if result.passed:
            passed_count += 1

    total_count = len(tests)

    print_header("Summary")
    print(f"Passed: {passed_count}/{total_count}")

    if passed_count == total_count:
        print("Smoke test passed.")
        return 0

    print("Smoke test failed.")
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Smoke test for BykeMania AI Operations Agent"
    )

    parser.add_argument(
        "--base-url",
        help="Base URL of the backend API. Example: http://127.0.0.1:8000"
    )

    args = parser.parse_args()

    base_url = get_base_url(args.base_url)
    api_key = get_api_key()

    return run_smoke_tests(
        base_url=base_url,
        api_key=api_key
    )


if __name__ == "__main__":
    sys.exit(main())
from __future__ import annotations

import os

import httpx


def assert_status(url: str, expected: int) -> None:
    response = httpx.get(url, timeout=10.0)
    if response.status_code != expected:
        raise RuntimeError(f"{url} expected {expected}, got {response.status_code}: {response.text}")


def main() -> None:
    base_url = os.getenv("APP_BASE_URL", "http://app:8000")
    assert_status(f"{base_url}/healthz", 200)
    assert_status(f"{base_url}/readyz", 200)
    print("verify_smoke: /healthz and /readyz ok")


if __name__ == "__main__":
    main()

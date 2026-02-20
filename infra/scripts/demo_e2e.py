from __future__ import annotations

import os

import httpx


def main() -> None:
    base_url = os.getenv("APP_BASE_URL", "http://app:8000")
    response = httpx.get(f"{base_url}/healthz", timeout=10.0)
    response.raise_for_status()
    print("Phase 0 demo smoke ok:", response.json())


if __name__ == "__main__":
    main()


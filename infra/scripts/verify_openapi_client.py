from __future__ import annotations

import importlib
import json
import os
import sys
from pathlib import Path
from typing import Any


def _load_openapi_schema(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise RuntimeError(f"missing openapi schema: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise RuntimeError("openapi schema must be an object")
    paths = data.get("paths")
    if not isinstance(paths, dict) or "/healthz" not in paths:
        raise RuntimeError("openapi schema missing required /healthz path")
    return data


def _find_postman_collection(path: Path) -> Path:
    if not path.exists():
        raise RuntimeError(f"missing postman output dir: {path}")
    files = sorted(item for item in path.glob("*.json") if item.is_file())
    if not files:
        raise RuntimeError("postman collection not generated")
    return files[0]


def _call_healthz(base_url: str, client_dir: Path) -> None:
    sys.path.insert(0, str(client_dir))
    openapi_client = importlib.import_module("openapi_client")

    configuration = openapi_client.Configuration(host=base_url)
    with openapi_client.ApiClient(configuration) as api_client:
        try:
            result = api_client.call_api(
                "GET",
                f"{base_url}/healthz",
            )
        except Exception as exc:
            raise RuntimeError(f"openapi client healthz call failed: {exc}") from exc

    status_code = int(getattr(result, "status", 0))
    if status_code == 0:
        raise RuntimeError("unexpected openapi client response shape")
    if status_code != 200:
        raise RuntimeError(f"healthz status expected 200, got {status_code}")


def main() -> None:
    root = Path.cwd()
    schema_path = root / "openapi" / "openapi.json"
    client_dir = root / "openapi" / "clients" / "python"
    postman_dir = root / "openapi" / "postman"

    _load_openapi_schema(schema_path)
    _find_postman_collection(postman_dir)
    if not (client_dir / "openapi_client").exists():
        raise RuntimeError("python client package not generated")

    base_url = os.getenv("APP_BASE_URL", "http://app:8000")
    _call_healthz(base_url, client_dir)
    print("verify_openapi_client: schema/artifacts/client smoke ok")


if __name__ == "__main__":
    main()

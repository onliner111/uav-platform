from __future__ import annotations

import json
from pathlib import Path

from app.main import app


def export_openapi(path: Path = Path("openapi/openapi.json")) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    schema = app.openapi()
    path.write_text(json.dumps(schema, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    export_openapi()


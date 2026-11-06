"""Write the FastAPI OpenAPI document for the frontend client generator."""

from __future__ import annotations

import json
from pathlib import Path

from app.main import app


def main() -> None:
    target = Path(__file__).resolve().parents[2] / "frontend" / "openapi.json"
    target.write_text(json.dumps(app.openapi(), indent=2) + "\n", encoding="utf-8")
    print(f"wrote {target} ({len(app.openapi()['paths'])} paths)")


if __name__ == "__main__":
    main()

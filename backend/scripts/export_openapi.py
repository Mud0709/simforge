"""Write the API's OpenAPI schema to disk (the contract the frontend types are generated from).

Usage: uv run python scripts/export_openapi.py [output_path]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from simforge.main import create_app

DEFAULT_OUTPUT = (
    Path(__file__).resolve().parents[2] / "frontend" / "src" / "lib" / "api" / "openapi.json"
)


def main() -> None:
    output = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_OUTPUT
    output.parent.mkdir(parents=True, exist_ok=True)
    schema = create_app().openapi()
    output.write_text(json.dumps(schema, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Wrote {output}")


if __name__ == "__main__":
    main()

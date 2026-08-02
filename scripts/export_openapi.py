import argparse
import json
from pathlib import Path

from afishabot.app import create_app


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export the non-public build-time OpenAPI contract"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("frontend/openapi/afisha.openapi.json"),
    )
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(create_app().openapi(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()

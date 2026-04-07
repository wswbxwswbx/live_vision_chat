from __future__ import annotations

import sys
from pathlib import Path

import uvicorn


def _bootstrap_pythonpath() -> None:
    root = Path(__file__).resolve().parents[2]
    entries = [
        root,
        root / "packages/protocol/src",
        root / "packages/runtime_store/src",
        root / "packages/runtime_core/src",
        root / "packages/execution/src",
        root / "packages/memory/src",
    ]
    for entry in reversed(entries):
        sys.path.insert(0, str(entry))


def main() -> None:
    _bootstrap_pythonpath()
    uvicorn.run("apps.gateway.app:create_app", factory=True, host="127.0.0.1", port=3000)


if __name__ == "__main__":
    main()

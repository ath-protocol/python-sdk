#!/usr/bin/env python3
"""Download the upstream ATH JSON Schema and meta.json.

Usage:
    python scripts/gen_schema.py

Downloads schema.json and meta.json from:
    https://github.com/ath-protocol/agent-trust-handshake-protocol/tree/main/schema/{version}

The version is read from schema/VERSION (default: 0.1).
"""
from __future__ import annotations

import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_DIR = ROOT / "schema"
VERSION_FILE = SCHEMA_DIR / "VERSION"

BASE_URL = "https://raw.githubusercontent.com/ath-protocol/agent-trust-handshake-protocol/refs/heads/main/schema"


def download(version: str = "0.1") -> None:
    """Fetch schema.json and meta.json from the upstream repo."""
    SCHEMA_DIR.mkdir(parents=True, exist_ok=True)
    for name in ("schema.json", "meta.json"):
        url = f"{BASE_URL}/{version}/{name}"
        dest = SCHEMA_DIR / ("ath-protocol.schema.json" if name == "schema.json" else name)
        print(f"Downloading {url} → {dest.relative_to(ROOT)}")
        urllib.request.urlretrieve(url, dest)
    VERSION_FILE.write_text(f"{version}\n")
    print("Done.")


def main() -> None:
    version = VERSION_FILE.read_text().strip() if VERSION_FILE.exists() else "0.1"
    download(version)


if __name__ == "__main__":
    main()

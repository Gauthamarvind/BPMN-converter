#!/usr/bin/env python3
"""
Fetch official BPMN 2.0 and Diagram Interchange XSD schemas from OMG.
Downloads schemas into backend/schemas/.
"""

import sys
import urllib.request
from pathlib import Path

SCHEMA_BASE_URL = "https://www.omg.org/spec/BPMN/20100501/"
SCHEMA_FILES = [
    "BPMN20.xsd",
    "Semantic.xsd",
    "BPMNDI.xsd",
    "DI.xsd",
    "DC.xsd",
]

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "backend" / "schemas"


def fetch_schemas() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Fetching BPMN 2.0 schemas into {OUTPUT_DIR}...")
    headers = {"User-Agent": "Mozilla/5.0 (Process2BPMN Schema Fetcher)"}

    for filename in SCHEMA_FILES:
        url = f"{SCHEMA_BASE_URL}{filename}"
        target_path = OUTPUT_DIR / filename
        print(f"Downloading {url} -> {target_path}...")
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=30) as resp:
            content = resp.read()
            target_path.write_bytes(content)
        print(f"  Saved {filename} ({len(content)} bytes)")

    print("All BPMN 2.0 schemas successfully fetched.")


if __name__ == "__main__":
    fetch_schemas()

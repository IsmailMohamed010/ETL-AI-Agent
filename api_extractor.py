"""
api_extractor.py
----------------
Core extraction engine.

Responsibilities:
  - Auto-detect the "shape" of an API response (flat, nested, list-of-dicts,
    list-of-scalars, wrapped envelope).
  - Flatten / normalise every shape into a tidy list-of-dicts.
  - Persist each result set as a UTF-8 CSV in the configured output folder.
  - Expose a single public helper `extract_api_to_csv()` called by main.py.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
import requests


# ──────────────────────────────────────────────────────────────────────────────
# Shape detection
# ──────────────────────────────────────────────────────────────────────────────

def _detect_shape(data: Any) -> str:
    """
    Classify the raw API payload into one of five canonical shapes.

    Shape            Example payload
    ─────────────────────────────────────────────────────────────────
    list_of_dicts    [{"id":1,"name":"Alice"}, {"id":2,"name":"Bob"}]
    list_of_scalars  [1, "foo", True]
    flat_dict        {"id":1,"name":"Alice","city":"NY"}
    nested_dict      {"user":{"id":1},"meta":{"created":"2024-01-01"}}
    wrapped          {"data":[...], "total":100, "page":1}
    empty_list       []
    unknown          anything else (scalar, None, etc.)
    """
    if isinstance(data, list):
        if not data:
            return "empty_list"
        if all(isinstance(item, dict) for item in data):
            return "list_of_dicts"
        return "list_of_scalars"

    if isinstance(data, dict):
        # Wrapped envelope: exactly ONE key holds a non-empty list of dicts
        list_keys = [
            k for k, v in data.items()
            if isinstance(v, list) and v and all(isinstance(i, dict) for i in v)
        ]
        if len(list_keys) == 1:
            return "wrapped"

        # Nested: at least one value is itself a dict
        if any(isinstance(v, dict) for v in data.values()):
            return "nested_dict"

        return "flat_dict"

    return "unknown"


# ──────────────────────────────────────────────────────────────────────────────
# Dict flattener
# ──────────────────────────────────────────────────────────────────────────────

def _flatten_dict(d: dict, parent_key: str = "", sep: str = ".") -> dict:
    """
    Recursively flatten a nested dict using dot-separated keys.

    Example:
        {"user": {"id": 1, "address": {"city": "Cairo"}}}
        → {"user.id": 1, "user.address.city": "Cairo"}

    Lists inside a dict are serialised as a JSON string to keep the CSV flat.
    """
    items: list[tuple[str, Any]] = []
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.extend(_flatten_dict(v, new_key, sep=sep).items())
        elif isinstance(v, list):
            items.append((new_key, json.dumps(v, ensure_ascii=False)))
        else:
            items.append((new_key, v))
    return dict(items)


# ──────────────────────────────────────────────────────────────────────────────
# Shape-specific normalisers
# ──────────────────────────────────────────────────────────────────────────────

def _normalise(data: Any, shape: str) -> list[dict]:
    """
    Convert any detected shape into a plain list[dict] ready for pd.DataFrame().
    """
    if shape == "list_of_dicts":
        return [_flatten_dict(row) for row in data]

    if shape == "list_of_scalars":
        return [{"index": idx, "value": item} for idx, item in enumerate(data)]

    if shape == "flat_dict":
        return [data]                       # single-row DataFrame

    if shape == "nested_dict":
        return [_flatten_dict(data)]        # one flattened row

    if shape == "wrapped":
        # The key that holds the list of records
        list_key = next(
            k for k, v in data.items()
            if isinstance(v, list) and v and all(isinstance(i, dict) for i in v)
        )
        rows = data[list_key]
        # Scalar metadata at the top level gets prefixed with _meta_
        meta = {
            f"_meta_{k}": v
            for k, v in data.items()
            if k != list_key and not isinstance(v, (dict, list))
        }
        return [{**_flatten_dict(row), **meta} for row in rows]

    if shape == "empty_list":
        return []

    # Fallback: store the whole payload as a raw JSON string
    return [{"raw": json.dumps(data, ensure_ascii=False)}]


# ──────────────────────────────────────────────────────────────────────────────
# File-naming helper
# ──────────────────────────────────────────────────────────────────────────────

def _safe_filename(url: str) -> str:
    """
    Derive a filesystem-safe stem from an endpoint URL.

    https://api.example.com/v1/users?page=1  →  v1_users
    https://api.example.com/forecast          →  forecast
    """
    path = re.sub(r"https?://[^/]+", "", url)    # drop scheme + host
    path = re.sub(r"\?.*$", "", path)             # drop query string
    path = re.sub(r"[^a-zA-Z0-9]+", "_", path).strip("_")
    return path or "extract"


# ──────────────────────────────────────────────────────────────────────────────
# CSV writer
# ──────────────────────────────────────────────────────────────────────────────

def _write_csv(records: list[dict], output_path: Path) -> Path:
    """Write records to *output_path* as a UTF-8 CSV and return the path."""
    df = pd.DataFrame(records)
    df.to_csv(output_path, index=False, encoding="utf-8")
    return output_path


# ──────────────────────────────────────────────────────────────────────────────
# Public entry-point
# ──────────────────────────────────────────────────────────────────────────────

def extract_api_to_csv(
    url: str,
    output_dir: str,
    filename: str | None = None,
    headers: dict | None = None,
    params: dict | None = None,
    timeout: int = 30,
) -> dict:
    """
    Fetch *url*, auto-detect its response shape, flatten it, and write a CSV.

    Parameters
    ----------
    url        : API endpoint to GET.
    output_dir : Directory where the CSV will be saved (created if missing).
    filename   : Optional explicit filename (no extension needed). If omitted,
                 one is derived from the URL + a timestamp.
    headers    : Optional HTTP request headers (e.g. {"Authorization": "Bearer ..."}).
    params     : Optional query-string parameters dict.
    timeout    : Request timeout in seconds (default 30).

    Returns
    -------
    A metadata dict:
        {
            "url"       : str,
            "shape"     : str,
            "row_count" : int,
            "col_count" : int,
            "csv_path"  : str | None,
            "columns"   : list[str],
            "status"    : "success" | "error",
            "message"   : str,
        }
    """
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # ── 1. Fetch ──────────────────────────────────────────────────────────────
    try:
        response = requests.get(
            url,
            headers=headers or {},
            params=params or {},
            timeout=timeout,
        )
        response.raise_for_status()
    except requests.exceptions.HTTPError as exc:
        return {
            "url": url, "status": "error",
            "message": f"HTTP {response.status_code}: {exc}",
        }
    except requests.RequestException as exc:
        return {"url": url, "status": "error", "message": str(exc)}

    # ── 2. Parse JSON ─────────────────────────────────────────────────────────
    try:
        data = response.json()
    except ValueError:
        return {
            "url": url, "status": "error",
            "message": "Response body is not valid JSON.",
        }

    # ── 3. Detect shape & normalise ───────────────────────────────────────────
    shape = _detect_shape(data)
    records = _normalise(data, shape)

    if not records:
        return {
            "url": url, "shape": shape,
            "row_count": 0, "col_count": 0,
            "csv_path": None, "columns": [],
            "status": "success",
            "message": "API returned an empty response — no CSV written.",
        }

    # ── 4. Build output path ──────────────────────────────────────────────────
    if filename:
        # Strip any extension the user may have added, then force .csv
        stem = Path(filename).stem
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        stem = f"{_safe_filename(url)}_{timestamp}"

    csv_path = out_dir / f"{stem}.csv"

    # ── 5. Write CSV ──────────────────────────────────────────────────────────
    _write_csv(records, csv_path)

    return {
        "url":       url,
        "shape":     shape,
        "row_count": len(records),
        "col_count": len(records[0]),
        "csv_path":  str(csv_path),
        "columns":   list(records[0].keys()),
        "status":    "success",
        "message":   f"Extracted {len(records)} rows → {csv_path.name}",
    }

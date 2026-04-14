"""
main.py
-------
Command-line entry point for the ETL extraction pipeline.

Fetches one or more REST API endpoints and saves each response as a CSV file.
No LLM / agent required — pure HTTP + pandas.

────────────────────────────────────────────────────────────────
USAGE
────────────────────────────────────────────────────────────────

  Single URL  (output folder is REQUIRED):
    python main.py --url <API_URL> --output <OUTPUT_FOLDER>

  Multiple URLs from a JSON file:
    python main.py --urls-file endpoints.json --output <OUTPUT_FOLDER>

  With optional Bearer-token auth:
    python main.py --url <API_URL> --output ./out --auth-token <TOKEN>

  With a custom filename (only valid for --url):
    python main.py --url <API_URL> --output ./out --filename my_data

────────────────────────────────────────────────────────────────
EXAMPLES
────────────────────────────────────────────────────────────────

  python main.py \
      --url https://jsonplaceholder.typicode.com/users \
      --output ./output

  python main.py \
      --urls-file endpoints.json \
      --output ./output

  python main.py \
      --url https://api.open-meteo.com/v1/forecast?latitude=30.06&longitude=31.24&current_weather=true \
      --output ./output \
      --filename cairo_weather

────────────────────────────────────────────────────────────────
endpoints.json FORMAT
────────────────────────────────────────────────────────────────

  [
    { "url": "https://jsonplaceholder.typicode.com/users" },
    { "url": "https://jsonplaceholder.typicode.com/posts", "filename": "posts" },
    {
      "url": "https://api.example.com/private",
      "auth_token": "Bearer sk-abc123"
    }
  ]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from api_extractor import extract_api_to_csv

# ─────────────────────────────────────────────────────────────────────────────
# Argument parser
# ─────────────────────────────────────────────────────────────────────────────

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="main.py",
        description="ETL API Extractor — fetch REST APIs and save as CSV",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    # ── Source (mutually exclusive: one URL OR a file of URLs) ────────────────
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument(
        "--url",
        metavar="URL",
        help="Single API endpoint URL to extract.",
    )
    source.add_argument(
        "--urls-file",
        metavar="FILE",
        help=(
            "Path to a JSON file containing an array of endpoint objects. "
            "Each object must have a 'url' key and may have optional "
            "'filename' and 'auth_token' keys."
        ),
    )

    # ── Output (required) ─────────────────────────────────────────────────────
    parser.add_argument(
        "--output",
        metavar="DIR",
        required=True,
        help="Output directory where CSV files will be written. Created if it does not exist.",
    )

    # ── Optional ──────────────────────────────────────────────────────────────
    parser.add_argument(
        "--filename",
        metavar="NAME",
        default=None,
        help=(
            "Base name for the output CSV (no extension). "
            "Only used with --url. "
            "Default: derived from the URL + timestamp."
        ),
    )
    parser.add_argument(
        "--auth-token",
        metavar="TOKEN",
        default=None,
        help=(
            "Bearer token for authenticated APIs. "
            "Sent as 'Authorization: Bearer <TOKEN>'. "
            "Only used with --url."
        ),
    )
    parser.add_argument(
        "--timeout",
        metavar="SECONDS",
        type=int,
        default=30,
        help="HTTP request timeout in seconds (default: 30).",
    )

    return parser


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _print_header(output_dir: Path, count: int) -> None:
    print()
    print("═" * 62)
    print("  ETL API Extractor")
    print("═" * 62)
    print(f"  Output folder : {output_dir}")
    print(f"  Endpoints     : {count}")
    print("═" * 62)
    print()


def _print_result(result: dict, index: int, total: int) -> None:
    prefix = f"  [{index}/{total}]"
    print(f"{prefix} {result['url']}")

    if result["status"] == "error":
        print(f"          ✗  ERROR  : {result['message']}")
    else:
        cols_preview = result["columns"][:6]
        cols_str = ", ".join(cols_preview)
        if len(result["columns"]) > 6:
            cols_str += f"  … +{len(result['columns']) - 6} more"

        print(f"          ✓  Shape   : {result['shape']}")
        print(f"          ✓  Rows    : {result['row_count']}")
        print(f"          ✓  Columns : {result['col_count']}  ({cols_str})")
        print(f"          ✓  Saved   : {result['csv_path']}")
    print()


def _print_summary(results: list[dict]) -> None:
    ok  = [r for r in results if r["status"] == "success"]
    err = [r for r in results if r["status"] == "error"]

    print("─" * 62)
    print(f"  Summary : {len(ok)} succeeded   {len(err)} failed")
    if err:
        print()
        print("  Failed endpoints:")
        for r in err:
            print(f"    • {r['url']}")
            print(f"      → {r['message']}")
    print("─" * 62)
    print()


# ─────────────────────────────────────────────────────────────────────────────
# Core runner
# ─────────────────────────────────────────────────────────────────────────────

def _run_extraction(endpoints: list[dict], output_dir: str, timeout: int) -> list[dict]:
    """
    Extract each endpoint dict and return a list of result dicts.

    Each endpoint dict must have:
        url        (str)  — required
        filename   (str)  — optional
        auth_token (str)  — optional  (will be sent as Bearer token)
    """
    results = []
    total = len(endpoints)

    for idx, ep in enumerate(endpoints, start=1):
        url        = ep["url"]
        filename   = ep.get("filename")
        auth_token = ep.get("auth_token")

        headers = {}
        if auth_token:
            # Support both raw tokens and already-prefixed "Bearer ..." strings
            if not auth_token.lower().startswith("bearer "):
                auth_token = f"Bearer {auth_token}"
            headers["Authorization"] = auth_token

        result = extract_api_to_csv(
            url=url,
            output_dir=output_dir,
            filename=filename,
            headers=headers if headers else None,
            timeout=timeout,
        )

        _print_result(result, idx, total)
        results.append(result)

    return results


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = _build_parser()
    args   = parser.parse_args()

    output_dir = Path(args.output).resolve()

    # ── Build endpoint list ───────────────────────────────────────────────────
    if args.url:
        endpoints = [{
            "url":        args.url,
            "filename":   args.filename,
            "auth_token": args.auth_token,
        }]

    else:  # --urls-file
        urls_file = Path(args.urls_file)
        if not urls_file.exists():
            print(f"\n  ERROR: File not found: {urls_file}", file=sys.stderr)
            print(  "  Create the file or use --url <URL> instead.", file=sys.stderr)
            sys.exit(1)

        try:
            with open(urls_file, encoding="utf-8") as fh:
                raw = json.load(fh)
        except json.JSONDecodeError as exc:
            print(f"\n  ERROR: Could not parse {urls_file}: {exc}", file=sys.stderr)
            sys.exit(1)

        if not isinstance(raw, list) or not raw:
            print(f"\n  ERROR: {urls_file} must contain a non-empty JSON array.", file=sys.stderr)
            sys.exit(1)

        # Validate each entry
        for i, ep in enumerate(raw):
            if not isinstance(ep, dict) or "url" not in ep:
                print(
                    f"\n  ERROR: Entry {i} in {urls_file} is missing the required 'url' key.",
                    file=sys.stderr,
                )
                sys.exit(1)

        endpoints = raw

    # ── Print header ──────────────────────────────────────────────────────────
    _print_header(output_dir, len(endpoints))

    # ── Run ───────────────────────────────────────────────────────────────────
    results = _run_extraction(endpoints, str(output_dir), args.timeout)

    # ── Summary ───────────────────────────────────────────────────────────────
    _print_summary(results)

    # Exit with a non-zero code if any extraction failed
    if any(r["status"] == "error" for r in results):
        sys.exit(1)


if __name__ == "__main__":
    main()

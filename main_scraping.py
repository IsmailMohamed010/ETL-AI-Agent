# main.py
"""
main.py
-------
Entry point for the Web Extraction Agent.
"""

import argparse
import json
import logging
import os
import subprocess
import sys
import time

import requests

from agentstate import WebAgentState
from graph import build_graph
from web_logic import _OUTPUT_DIR

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)


# ── Ollama health check + auto-start ──────────────────────────────────────────

def _ensure_ollama_running() -> bool:
    """Check if Ollama is running. If not, start it automatically."""

    # Step 1: already running?
    try:
        r = requests.get("http://localhost:11434", timeout=3)
        if r.status_code == 200:
            logger.info("Ollama is already running.")
            return True
    except Exception:
        pass

    # Step 2: not running — start it
    print("  ⚡  Ollama not running — starting it automatically...")
    try:
        kwargs = {"stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL}
        if os.name == "nt":                               # Windows: no popup terminal
            kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
        subprocess.Popen(["ollama", "serve"], **kwargs)
    except FileNotFoundError:
        print("  ❌  Ollama not found. Is it installed?")
        print("      Download from: https://ollama.com/download")
        return False
    except Exception as exc:
        logger.error("Failed to start Ollama: %s", exc)
        return False

    # Step 3: wait up to 15 seconds for it to be ready
    print("  ⏳  Waiting for Ollama to start", end="", flush=True)
    for _ in range(15):
        time.sleep(1)
        print(".", end="", flush=True)
        try:
            r = requests.get("http://localhost:11434", timeout=2)
            if r.status_code == 200:
                print(" ready!")
                logger.info("Ollama started successfully.")
                return True
        except Exception:
            pass

    print(" timed out.")
    print("  ❌  Ollama did not start in time. Try running 'ollama serve' manually.")
    return False


# ── URL validation + auto-fix ─────────────────────────────────────────────────

def _normalize_url(url: str) -> str:
    """Fix common URL mistakes before passing to Playwright."""
    url = url.strip()
    if url.startswith("//"):
        url = "https:" + url
        print(f"  ℹ️   Auto-corrected URL to: {url}")
    elif not url.startswith(("http://", "https://")):
        url = "https://" + url
        print(f"  ℹ️   Auto-corrected URL to: {url}")
    return url


# ── CLI args ──────────────────────────────────────────────────────────────────

def parse_args():
    parser = argparse.ArgumentParser(
        description="Web Extraction Agent — scrape → extract → parse → save"
    )
    parser.add_argument("--url",             default=None,        help="Website URL to scrape")
    parser.add_argument("--query",           default=None,        help="What to extract")
    parser.add_argument("--wait-selector",   default=None,        help="CSS selector to wait for")
    parser.add_argument("--infinite-scroll", action="store_true", help="Enable infinite scroll")
    parser.add_argument("--no-csv",          action="store_true", help="Skip CSV output")
    parser.add_argument("--no-db",           action="store_true", help="Skip SQLite output")
    parser.add_argument("--show-all",        action="store_true", help="Print all extracted rows")
    parser.add_argument("--ollama-model",    default="llama3",    help="Ollama model for prompt generation (default: llama3)")
    return parser.parse_args()


# ── Main ──────────────────────────────────────────────────────────────────────

def main():

    # 1. Ensure Ollama is running before anything else
    if not _ensure_ollama_running():
        return 1

    args = parse_args()

    # 2. Set Ollama model for prompt generator
    import prompt_generator
    prompt_generator.OLLAMA_MODEL = args.ollama_model

    # 3. Get URL
    url = args.url
    if not url:
        url = input("🌐  Enter website URL to scrape: ").strip()
        if not url:
            print("Error: URL is required.")
            return 1
    url = _normalize_url(url)

    # 4. Get extraction query
    search_query = args.query
    if not search_query:
        search_query = input("🔍  What do you want to extract? ").strip()
        if not search_query:
            search_query = "all important information on this page"

    # 5. Build initial state
    initial_state: WebAgentState = {
        "url":          url,
        "search_query": search_query,
        "config": {
            "wait_selector":   args.wait_selector,
            "infinite_scroll": args.infinite_scroll,
            "save_csv":        not args.no_csv,
            "save_db":         not args.no_db,
        },
        "raw_content":    "",
        "extracted_json": [],
        "parsed_rows":    [],
        "errors":         [],
        "status":         "init",
    }

    print("\n" + "═" * 60)
    print("  WEB EXTRACTION AGENT")
    print("═" * 60)
    print(f"  URL   : {url}")
    print(f"  Query : {search_query}")
    print("═" * 60 + "\n")

    # 6. Run pipeline
    app         = build_graph()
    final_state = app.invoke(initial_state)

    status = final_state.get("status")
    rows   = final_state.get("parsed_rows", [])
    errors = final_state.get("errors", [])

    # 7. Print results
    print("\n" + "═" * 60)
    print("  RESULT")
    print("═" * 60)
    print(f"  Status  : {status}")
    print(f"  Rows    : {len(rows)}")

    if errors:
        for e in errors:
            print(f"    • {e}")

    if rows:
        display_rows = rows if args.show_all else rows[:5]
        if not args.show_all and len(rows) > 5:
            print(f"\n📋  Showing first 5 of {len(rows)} rows (use --show-all to see all):")
        else:
            print(f"\n📋  Extracted rows ({len(rows)} total):")
        for i, row in enumerate(display_rows, 1):
            fields = {k: v for k, v in row.items() if k != "_source_url" and v is not None}
            print(f"  {i:>3}. {json.dumps(fields, ensure_ascii=False)}")

    if status == "done":
        print("\n✅  Pipeline complete!")
    else:
        print("\n❌  Agent did not complete successfully.")

    print(f"\n  📁  Output folder : {_OUTPUT_DIR}")
    print(f"  📄  CSV           → {os.path.join(_OUTPUT_DIR, 'results.csv')}")
    print(f"  🗄️   DB            → {os.path.join(_OUTPUT_DIR, 'results.db')}")

    return 0 if status == "done" else 1


if __name__ == "__main__":
    sys.exit(main())

# web_logic.py
"""
web_logic.py
------------
Playwright-based scraper + CSV/SQLite save helpers.
"""

import logging
import os
import re
import sqlite3

import pandas as pd
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

logger = logging.getLogger(__name__)

_SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
_PROJECT_DIR = os.path.dirname(_SCRIPT_DIR)
_OUTPUT_DIR  = os.path.join(_PROJECT_DIR, "output")


# ── Scroll helper ──────────────────────────────────────────────────────────────

def _scroll_to_bottom_playwright(page, pause_ms: int = 2000) -> None:
    last_height = page.evaluate("document.body.scrollHeight")
    while True:
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        page.wait_for_timeout(pause_ms)
        new_height = page.evaluate("document.body.scrollHeight")
        if new_height == last_height:
            break
        last_height = new_height


# ── HTML → clean text ──────────────────────────────────────────────────────────

def _html_to_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")

    # Step 1: replace truncated <a> text with full title attribute
    for a_tag in soup.find_all("a", title=True):
        full_title = a_tag["title"].strip()
        if full_title:
            a_tag.string = full_title

    # Step 2: replace <img> with alt text
    for img in soup.find_all("img", alt=True):
        alt_text = img["alt"].strip()
        if alt_text:
            img.replace_with(alt_text)

    # Step 3: strip boilerplate
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()

    text = soup.get_text(separator="\n", strip=True)

    # Step 4: strip Wikipedia-style footnote markers: [a], [b], [1], [note 1]
    text = re.sub(r'\[[a-zA-Z0-9 ]{1,10}\]', '', text)

    return text


# ── Output helpers ─────────────────────────────────────────────────────────────

def _ensure_output_dir() -> None:
    os.makedirs(_OUTPUT_DIR, exist_ok=True)


def _resolve_path(filename: str) -> str:
    return os.path.join(_OUTPUT_DIR, filename)


# ── Main scrape ────────────────────────────────────────────────────────────────

def scrape_page(
    url: str,
    wait_selector: str | None = None,
    infinite_scroll: bool = False,
) -> str:
    """Scrape a single URL using Playwright. Returns clean plain text."""
    with sync_playwright() as p:
        # Initialize to None so finally block is safe even if launch() fails
        browser = None
        try:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0 Safari/537.36"
                ),
                viewport={"width": 1920, "height": 1080},
                extra_http_headers={
                    "Accept-Language": "en-US,en;q=0.9",
                    "Accept-Encoding": "gzip, deflate, br",
                },
            )
            page = context.new_page()
            page.add_init_script(
                "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
            )

            logger.info("Scraping: %s", url)

            # domcontentloaded is fast and reliable.
            # networkidle attempted as best-effort — many real sites never settle.
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            try:
                page.wait_for_load_state("networkidle", timeout=8000)
            except PlaywrightTimeout:
                logger.info("networkidle not reached — continuing with domcontentloaded.")

            if wait_selector:
                try:
                    page.wait_for_selector(wait_selector, timeout=10000)
                except PlaywrightTimeout:
                    logger.warning("Timeout: element '%s' not found within 10s", wait_selector)

            if infinite_scroll:
                _scroll_to_bottom_playwright(page)

            page.wait_for_timeout(500)
            html = page.content()
            text = _html_to_text(html)
            logger.info("Scraped %d characters.", len(text))
            return text

        finally:
            if browser:
                browser.close()


# ── Save to CSV ────────────────────────────────────────────────────────────────

def save_to_csv(rows: list[dict], path: str = "") -> None:
    _ensure_output_dir()
    out = path if os.path.isabs(path) else _resolve_path(path or "results.csv")

    df = pd.DataFrame(rows)

    # Clean float columns that are whole numbers (e.g. 1425423212.0 → 1425423212)
    for col in df.columns:
        if df[col].dtype == float:
            if df[col].dropna().apply(lambda x: x == int(x)).all():
                df[col] = df[col].fillna("").apply(
                    lambda x: str(int(x)) if x != "" else ""
                )

    df.to_csv(out, index=False, encoding="utf-8-sig")
    logger.info("Saved CSV → %s  (%d rows)", out, len(rows))
    print(f"  📄  CSV  → {out}")


# ── Save to SQLite ─────────────────────────────────────────────────────────────

def _get_existing_columns(cur: sqlite3.Cursor, table: str) -> list[str]:
    cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)
    )
    if not cur.fetchone():
        return []
    cur.execute(f"PRAGMA table_info({table})")
    return [row[1] for row in cur.fetchall() if row[1] != "id"]


def save_to_db(rows: list[dict], db_path: str = "") -> None:
    if not rows:
        logger.warning("No rows to save to DB.")
        return
    _ensure_output_dir()
    out = db_path if os.path.isabs(db_path) else _resolve_path(db_path or "results.db")

    conn = sqlite3.connect(out)
    cur  = conn.cursor()

    new_cols      = list(rows[0].keys())
    existing_cols = _get_existing_columns(cur, "results")

    if existing_cols and set(existing_cols) != set(new_cols):
        logger.warning("DB schema changed — dropping old table.")
        cur.execute("DROP TABLE results")
        existing_cols = []

    if not existing_cols:
        col_defs = ", ".join(f'"{c}" TEXT' for c in new_cols)
        cur.execute(f"""
            CREATE TABLE results (
                id   INTEGER PRIMARY KEY AUTOINCREMENT,
                {col_defs}
            )
        """)

    placeholders = ", ".join("?" * len(new_cols))
    col_names    = ", ".join(f'"{c}"' for c in new_cols)
    cur.executemany(
        f"INSERT INTO results ({col_names}) VALUES ({placeholders})",
        [tuple(str(r.get(c, "")) for c in new_cols) for r in rows],
    )

    conn.commit()
    conn.close()
    logger.info("Saved DB  → %s  (%d rows)", out, len(rows))
    print(f"  🗄️   DB   → {out}")

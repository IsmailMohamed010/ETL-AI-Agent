from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import pandas as pd
import time
import logging
import sqlite3
import random

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)


# --- Create Selenium driver ---
def create_driver():
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("user-agent=Mozilla/5.0")
    driver = webdriver.Chrome(options=options)
    return driver



def scrap_pagination(base_url, start_page, end_page, wait_selector=None, infinite_scroll=False):
    """
    base_url: URL with {} for page numbers
    wait_selector: CSS selector to wait for JS-loaded content
    infinite_scroll: if True, scrolls to bottom to load all content
    """
    pages = []
    driver = create_driver()
    total_pages = end_page - start_page + 1

    for idx, page in enumerate(range(start_page, end_page + 1), start=1):
        url = base_url.format(page)
        logging.info(f"Scraping page {idx} of {total_pages}: {url}")
        driver.get(url)

        
        if wait_selector:
            try:
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, wait_selector))
                )
            except:
                logging.warning(f"Waited 10s, element '{wait_selector}' not found on {url}")

       
        if infinite_scroll:
            SCROLL_PAUSE_TIME = 2
            last_height = driver.execute_script("return document.body.scrollHeight")
            while True:
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(SCROLL_PAUSE_TIME)
                new_height = driver.execute_script("return document.body.scrollHeight")
                if new_height == last_height:
                    break
                last_height = new_height

        html = driver.page_source
        soup = BeautifulSoup(html, "html.parser")

        
        for s in soup(["script", "style"]):
            s.extract()

        
        text = soup.get_text(separator="\n", strip=True)

        pages.append({
            "url": url,
            "content": text
        })

        # Random delay between pages to avoid anti-bot detection
        time.sleep(random.uniform(1, 3))

    driver.quit()
    return pd.DataFrame(pages)



def extract_from_web(state, wait_selector=None, infinite_scroll=False):
    config = state["config"]
    base_url = state["urls"][0]["url"]
    p = config["pagination"]

    df = scrap_pagination(
        base_url=base_url,
        start_page=p["start"],
        end_page=p["end"],
        wait_selector=wait_selector,
        infinite_scroll=infinite_scroll
    )

    return {
        "extracted_data": df.to_dict(orient="records")
    }


# --- Save CSV ---
def save_extracted_result(data):
    df = pd.DataFrame(data)
    df.to_csv("web_results.csv", index=False, encoding="utf-8")
    print("Saved CSV → web_results.csv")


# --- Save SQLite DB ---
def save_extracted_result_db(data):
    conn = sqlite3.connect("web_results.db")
    cursor = conn.cursor()

    # Create table if not exists
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT,
            content TEXT
        )
    """)

    # Insert each page
    cursor.executemany("""
        INSERT INTO results (url, content)
        VALUES (:url, :content)
    """, data)

    conn.commit()
    conn.close()
    print("Saved to Database → web_results.db")


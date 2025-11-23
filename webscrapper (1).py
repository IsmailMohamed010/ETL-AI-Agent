from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from bs4 import BeautifulSoup
import pandas as pd
import time
import logging
from urllib.parse import urljoin



logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)


def create_driver():
    options = Options()
    options.add_argument("--headless")  
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("user-agent=Mozilla/5.0")

    driver = webdriver.Chrome(options=options)
    return driver



def scrape_page(url, parent_tag, parent_class, fields, timeout=10):

    driver = create_driver()

    logging.info(f"Opening URL with Selenium: {url}")
    driver.get(url)
    time.sleep(2)  

    html = driver.page_source
    driver.quit()

    soup = BeautifulSoup(html, "html.parser")

    # find all item containers
    if parent_class:
        items = soup.find_all(parent_tag, class_=parent_class)
    else:
        items = soup.find_all(parent_tag)

    logging.info(f"Found {len(items)} items")

    rows = []

    for item in items:
        row = {}
        for out_col, (tag, attr) in fields.items():
            elem = item.find(tag)

            if elem:
                if attr == "text":
                    row[out_col] = elem.get_text(strip=True)
                else:
                    row[out_col] = elem.get(attr)

                # convert relative URLs to absolute
                if attr in ["href", "src"] and row[out_col]:
                    row[out_col] = urljoin(url, row[out_col])
            else:
                row[out_col] = None

        rows.append(row)

    return pd.DataFrame(rows)



def scrape_with_pagination(start_page, end_page, parent_tag, parent_class, fields):

    all_pages = []

    for page in range(start_page, end_page + 1):

        url = f"https://books.toscrape.com/catalogue/page-{page}.html"
        logging.info(f"Scraping page {page}: {url}")

        df = scrape_page(
            url=url,
            parent_tag=parent_tag,
            parent_class=parent_class,
            fields=fields
        )

        if df.empty:
            logging.warning(f"No items found on page {page}. Stopping.")
            break

        all_pages.append(df)
        time.sleep(1)

    if not all_pages:
        return pd.DataFrame()

    return pd.concat(all_pages, ignore_index=True)



def extract_data(config):

    parent_tag = config["parent_tag"]
    parent_class = config.get("parent_class")
    fields = config["fields"]
    output_path = config.get("output_path", "output.csv")

    fields = {k: tuple(v) for k, v in fields.items()}

    p = config["pagination"]

    df = scrape_with_pagination(
        start_page=p["start"],
        end_page=p["end"],
        parent_tag=parent_tag,
        parent_class=parent_class,
        fields=fields
    )

    df.to_csv(output_path, index=False)
    logging.info(f"Saved {len(df)} rows → {output_path}")

    return df



if __name__ == "__main__":
    config = {
        "pagination": {
            "enabled": True,
            "start": 1,
            "end": 3
        },
        "parent_tag": "article",
        "parent_class": "product_pod",
        "fields": {
            "title": ["h3", "text"],
            "price": ["p", "text"],
            "link": ["a", "href"]
        },
        "output_path": "books.csv"
    }

    df = extract_data(config)
    print(df.head())


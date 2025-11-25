from agentstate import AgentState
from web_logic import extract_from_web, save_extracted_result, save_extracted_result_db

if __name__ == "__main__":

    state: AgentState = {
    "urls": [
        {
            "url": "https://books.toscrape.com/catalogue/page-{}.html",
            "doc_type": "html"
        }
    ],
    "config": {
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
        }
    }
}


    result = extract_from_web(state)
    print(result)

    save_extracted_result(result["extracted_data"])
    save_extracted_result_db(result["extracted_data"])

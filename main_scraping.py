from agentstate import AgentState
from web_logic import extract_from_web, save_extracted_result, save_extracted_result_db

if __name__ == "__main__":

    # --- Define scraping state ---
    state = {
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
            }
        }
    }

    
    wait_selector = None  
   
    infinite_scroll = False

   
    result = extract_from_web(
        state,
        wait_selector=wait_selector,
        infinite_scroll=infinite_scroll
    )

  
    save_extracted_result(result["extracted_data"])

  
    save_extracted_result_db(result["extracted_data"])


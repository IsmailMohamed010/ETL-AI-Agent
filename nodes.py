from typing import Dict, Any
from web_logic import extract_from_web, save_extracted_result, save_extracted_result_db

def node_extract(state: Dict[str, Any]) -> Dict[str, Any]:
    try:
        cfg = state["config"]
        result = extract_from_web(
            state,
            wait_selector=cfg.get("wait_selector"),
            infinite_scroll=cfg.get("infinite_scroll", False)
        )
        return {
            "extracted_data": result["extracted_data"],
            "status": "running"
        }
    except Exception as e:
        return {
            "errors": state.get("errors", []) + [str(e)],
            "status": "failed"
        }

def node_validate(state: Dict[str, Any]) -> Dict[str, Any]:
    data = state.get("extracted_data", [])
    if not data:
        return {"errors": state.get("errors", []) + ["No extracted data"], "status": "failed"}
    return {"status": "running"}

def node_save(state: Dict[str, Any]) -> Dict[str, Any]:
    cfg = state["config"]
    data = state.get("extracted_data", [])

    if cfg.get("save_csv", True):
        save_extracted_result(data)

    if cfg.get("save_db", True):
        save_extracted_result_db(data)

    return {"status": "done"}

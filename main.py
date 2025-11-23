from agentstate import AgentState
from logic import extract_files, save_extracted_result, save_extracted_result_db

if __name__ == "__main__":
    state: AgentState = {
        "files": [
            {"file_path": "test_data/amazon.csv", "doc_type": "file"},
            {"file_path": "test_data/multi_sheet_demo.xlsx", "doc_type": "file"}
        ]
    }

    result = extract_files(state)
    print(result)
    
    save_extracted_result(result["extracted_data"])
    save_extracted_result_db(result["extracted_data"])

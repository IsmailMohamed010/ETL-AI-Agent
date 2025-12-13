from agentstate import AgentState
from detect_excel_relations import detect_excel_relationships, print_detected_relationships
from save_files import save_extracted_result_db, save_extracted_result_csv, save_relations_json
from extract_files import extract_files

state: AgentState = {
    "files": [
        {"file_path": "test_data/multi_sheet_demo.xlsx", "doc_type": "file"},
        {"file_path": "test_data/multi_sheet_demo - Copy.xlsx", "doc_type": "file"},
    ]
}

result = extract_files(state)

if "extracted_data" not in result or not result["extracted_data"]:
    print("❌ No data extracted. Exiting.")
    exit(1)

extracted_data = result["extracted_data"]

state_relationship = detect_excel_relationships({"extracted_data": extracted_data})
print_detected_relationships(state_relationship)
save_relations_json(state_relationship.get("detected_relations", {}))
save_extracted_result_csv(extracted_data)

save_extracted_result_db(extracted_data)

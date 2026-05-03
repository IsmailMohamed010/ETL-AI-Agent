from typing import Annotated
from typing_extensions import TypedDict


class FileMeta(TypedDict):
    file_path: str | None
    doc_type: str | None

class AgentState(TypedDict):
    files: Annotated[list[FileMeta], "file"]
    extracted_data: dict | None  # هيتخزن بعد extract_files_node
    detected_relations: dict | None  # هيتخزن بعد detect_excel_relationships

from typing import Annotated
from typing_extensions import TypedDict


class FileMeta(TypedDict):
    """Minimal file metadata shape. Add or change fields as needed."""
    file_path: str | None
    doc_type: str | None


class AgentState(TypedDict):
    files: Annotated[list[FileMeta], "file"]
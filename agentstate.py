from typing import Annotated, Any, Optional
from typing_extensions import TypedDict

class WebMeta(TypedDict):
    url: str
    doc_type: str  # "html" | "pdf" | "json" etc.

class PaginationConfig(TypedDict):
    enabled: bool
    start: int
    end: int

class AgentConfig(TypedDict):
    pagination: PaginationConfig
    wait_selector: Optional[str]
    infinite_scroll: bool
    save_csv: bool
    save_db: bool

class WebAgentState(TypedDict, total=False):
    # inputs
    urls: Annotated[list[WebMeta], "web"]
    config: AgentConfig

    # outputs
    extracted_data: list[dict]     
    errors: list[str]
    status: str                   

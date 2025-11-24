from typing import Annotated
from typing_extensions import TypedDict



class WebMeta(TypedDict):
    url: str | None
    doc_type: str | None



class WebAgentState(TypedDict):
    urls: Annotated[list[WebMeta], "web"]

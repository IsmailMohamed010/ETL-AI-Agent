from typing import Annotated
from typing_extensions import TypedDict


# Metadata for each web page
class WebMeta(TypedDict):
    url: str | None
    doc_type: str | None


# Agent State for Web Scraping
class WebAgentState(TypedDict):
    urls: Annotated[list[WebMeta], "web"]

from typing import TypedDict, Annotated, List
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class GeoState(TypedDict):
    messages: Annotated[List[BaseMessage], add_messages]
    retrieved_context: List[dict]
    top_gse_ids: List[str]

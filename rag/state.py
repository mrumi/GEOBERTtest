# ============================================================
# rag/state.py — GeoState (LangGraph State Definition)
# ============================================================
# This is a pure
# data structure with no external dependencies.
# ============================================================

from typing import TypedDict, Annotated
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class GeoState(TypedDict):

    # ── Conversation Messages ──────────────────────────────
    messages: Annotated[list[BaseMessage], add_messages]

    # ── Query Understanding Output ─────────────────────────
    # intent, operations, filters, concepts,
    # semantic_focus_fields, query_type,
    # logical_operator, resolved_organism,
    # strategy, confidence
    query_info: dict

    # ── Raw Retrieval Results ──────────────────────────────
    retrieved_context: list

    # ── Reranked Results (study-level, aggregated) ─────────
    reranked_context: list

    # ── Sample-Level Context (independent retrieval) ───────
    sample_context: list

    # ── Top GSE IDs ─────────────────────────────────────────
    top_gse_ids: list

    # ── Dropped Filters ──────────────────────────────────────
    dropped_filters: dict

    # ── Session Memory ──────────────────────────────────────
    # List of prior turns in this session, used by
    # rag/query_understanding.py for multi-turn follow-up
    # handling. Each entry:
    #   {"query": str, "filters": dict, "concepts": list}
    session_memory: list
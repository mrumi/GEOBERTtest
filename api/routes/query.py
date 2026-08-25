# ============================================================
# api/routes/query.py — Main Query Endpoint
# ============================================================
# This route additionally
# handles: session ownership/creation, multi-turn session_memory
# loading from the DB, and persisting both turns as Message rows).
# ============================================================

import uuid
import json as _json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from langchain_core.messages import HumanMessage

from core.database import get_db
from core.config import Settings
from core.clients import AppClients
from api.dependencies import get_current_user, get_clients, get_organism_resolver, get_settings
from models.user import User
from models.session import ChatSession
from models.message import Message
from api.schemas import QueryRequest, QueryResponse, StudyResult, SampleResult

from rag.rag_node import rag_node
from rag.answer_generator import generate_answer
from rag.sparse_vector import generate_sparse_vector
from rag.result_aggregator import build_dashboard_stats

router = APIRouter(prefix="/query", tags=["query"])


def _short_title(query: str, max_chars: int = 42) -> str:
    """
    Session title from the query that started it. Short queries are kept whole;
    longer ones are cut at the last whole word under max_chars.
    """
    query = query.strip()
    if len(query) <= max_chars:
        return query
    return query[:max_chars].rsplit(" ", 1)[0] + "…"


def _build_session_memory(session: ChatSession) -> list[dict]:
    memory = []
    pending_query = None

    for msg in session.messages:
        if msg.role == "user":
            pending_query = msg.content
        elif msg.role == "assistant" and pending_query is not None:
            query_info = msg.query_info or {}
            memory.append({
                "query"   : pending_query,
                "filters" : query_info.get("filters", {}),
                "concepts": query_info.get("concepts", []),
            })
            pending_query = None

    return memory


@router.post("", response_model=QueryResponse)
async def run_query(
    payload      : QueryRequest,
    db           : AsyncSession = Depends(get_db),
    current_user : User = Depends(get_current_user),
    clients      : AppClients = Depends(get_clients),
    organism_resolver = Depends(get_organism_resolver),
    settings     : Settings = Depends(get_settings),
):
    # ── Resolve or create the session ──────────────────────
    if payload.session_id is not None:
        result = await db.execute(
            select(ChatSession)
            .where(ChatSession.id == payload.session_id, ChatSession.user_id == current_user.id)
            .options(selectinload(ChatSession.messages))
        )
        session = result.scalar_one_or_none()
        if session is None:
            raise HTTPException(status_code=404, detail="Session not found")

        session_memory = _build_session_memory(session)

    else:
        session = ChatSession(
            user_id=current_user.id,
            title=_short_title(payload.query)
        )
        db.add(session)
        await db.flush()
        session_memory = []

    # ── Run the RAG pipeline ───────────────────────────────
    state = {
        "messages"       : [HumanMessage(content=payload.query)],
        "session_memory" : session_memory,
    }

    rag_output = rag_node(
        state                      = state,
        qdrant_client              = clients.qdrant_client,
        groq_client                = clients.groq_client,
        dense_embedder             = clients.dense_embedder,
        cross_encoder              = clients.cross_encoder,
        generate_sparse_vector_fn  = lambda text: generate_sparse_vector(text, clients.sparse_embedder),
        organism_resolver          = organism_resolver,
        settings                   = settings,
    )

    answer = generate_answer(
        query             = payload.query,
        query_info        = rag_output["query_info"],
        reranked_context  = rag_output["reranked_context"],
        groq_client       = clients.groq_client,
        groq_answer_model = settings.GROQ_ANSWER_MODEL,
        sample_context    = rag_output.get("sample_context", []),
        dropped_filters   = rag_output.get("dropped_filters", {}),
    )

    # ── Build the result snapshot BEFORE persisting, so it can be
    #    attached to the assistant Message row ─────────
    studies = [
        StudyResult(
            gse_id           = study["gse_id"],
            relevance_score  = study["relevance_score"],
            geo_link         = f"https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc={study['gse_id']}",
            organism         = study["metadata"].get("organism", ""),
            tissue           = study["metadata"].get("tissue", ""),
            assay_type       = study["metadata"].get("assay_type", ""),
            library_strategy = study["metadata"].get("library_strategy", ""),
            fields_found     = list(study["fields"].keys()),
            is_superseries   = study["metadata"].get("is_superseries", False),
            is_subseries     = study["metadata"].get("is_subseries", False),
            parent_series_id = study["metadata"].get("parent_series_id", ""),
            subseries_ids    = study["metadata"].get("subseries_ids", []),
        )
        for study in rag_output["reranked_context"]
    ]

    samples = [
            SampleResult(
                gse_id   = hit["payload"].get("gse_id", ""),
                gsm_id   = hit["payload"].get("gsm_id", ""),
                relevance_score  = hit.get("relevance_score"),
                title    = hit["payload"].get("title", ""),
                organism = hit["payload"].get("organism", ""),
                library_strategy = hit["payload"].get("library_strategy", ""),
                cell_line = hit["payload"].get("cell_line", ""),
                cell_type = hit["payload"].get("cell_type", ""),
                tissue   = hit["payload"].get("tissue", ""),
                disease  = hit["payload"].get("disease", ""),
                genotype = hit["payload"].get("genotype", ""),
            )
            for hit in rag_output.get("sample_context", [])
        ]

    query_info = rag_output["query_info"]

    dashboard_stats = build_dashboard_stats(
        reranked_context = rag_output["reranked_context"],
        sample_context   = rag_output.get("sample_context", []),
        query_info       = query_info,
        dropped_filters  = rag_output.get("dropped_filters", {}),
    )

    # ── Persist both turns — assistant turn now carries its
    #    own result snapshot ──────────────────────────────────
    user_message = Message(session_id=session.id, role="user", content=payload.query)
    assistant_message = Message(
        session_id      = session.id,
        role            = "assistant",
        content         = answer,
        query_info      = query_info,
        dropped_filters = rag_output.get("dropped_filters", {}),
        top_gse_ids     = rag_output.get("top_gse_ids", []),
        studies         = [s.model_dump() for s in studies],
        samples         = [s.model_dump() for s in samples],
        dashboard_stats = dashboard_stats,
    )
    db.add_all([user_message, assistant_message])

    if session.title == "New session":
        session.title = _short_title(payload.query)

    await db.commit()
    await db.refresh(session)

    return QueryResponse(
        session_id      = session.id,
        query           = payload.query,
        answer          = answer,
        intent          = query_info.get("intent", ""),
        query_type      = query_info.get("query_type", ""),
        strategy        = query_info.get("strategy", ""),
        filters         = query_info.get("filters", {}),
        dropped_filters = rag_output.get("dropped_filters", {}),
        top_gse_ids     = rag_output.get("top_gse_ids", []),
        studies         = studies,
        samples         = samples,
        dashboard_stats = dashboard_stats,
    )
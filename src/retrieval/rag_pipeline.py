from typing import Any, Dict, List
from src.types import GeoState
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue, MatchAny

from src.config import TOP_K_STUDY, TOP_K_SAMPLE, SIM_THRESHOLD
from .bm25_index import BM25Index
from .hybrid_search import hybrid_search_collection
from .query_analyzer import analyze_query
from .sample_expansion import build_sample_context


def _payload_get(payload: dict, field: str):
    # Same helper logic as Cell 4.5
    if payload is None:
        return None
    if field in payload and payload[field] not in (None, "", []):
        return payload[field]
    meta = payload.get("metadata")
    if isinstance(meta, dict):
        return meta.get(field)
    return None


def _apply_soft_boost(hits: list, filters: dict, per_match_bonus: float = 0.03) -> list:
    """
    Qdrant Filter doesn't "boost" scores; it only filters.
    So we do boosting post-retrieval by adding a small bonus to final_score.
    """
    if not hits or not filters:
        return hits

    for h in hits:
        p = h.get("payload", {}) or {}
        bonus = 0.0
        for f, v in filters.items():
            pv = _payload_get(p, f)
            if pv is None:
                continue
            pv_norm = str(pv).strip().lower()
            if pv_norm == str(v).strip().lower():
                bonus += per_match_bonus
        h["final_score"] = float(h.get("final_score", 0.0)) + bonus

    # re-sort
    hits.sort(key=lambda x: float(x.get("final_score", 0.0)), reverse=True)
    return hits


def rag_node(
    state: GeoState,
    *,
    qdrant_client,          # ✅ vector DB client
    groq_client,            # ✅ LLM client for parsing
    embedder: Any,
    study_collection: str,
    sample_collection: str,
    bm25_study: BM25Index,
    bm25_sample: BM25Index,
    metadata_index: dict,   # ✅ dataset-grounded vocab (build once)
    top_k_study: int = TOP_K_STUDY,
    top_k_sample: int = TOP_K_SAMPLE,
    sim_threshold: float = SIM_THRESHOLD
) -> GeoState:

    # 1) last user message text
    user_text = ""
    for msg in reversed(state["messages"]):
        if getattr(msg, "type", None) == "human" or msg.__class__.__name__ == "HumanMessage":
            user_text = msg.content
            break
    if not user_text:
        return {"retrieved_context": [], "top_gse_ids": []}

    # 2) Query understanding (BEFORE embedding)
    query_info = analyze_query(
        user_text,
        groq_client=groq_client,
        metadata_index=metadata_index
    )
    strategy = query_info.get("strategy", "SEMANTIC_ONLY")
    filters = query_info.get("filters", {}) or {}
    conf = query_info.get("confidence", {}) or {}

    print("Detected query_type:", query_info.get("query_type"))
    print("Strategy:", strategy, "| overall_conf:", conf.get("overall_confidence"))
    print("Grounded filters:", filters)
    if query_info.get("dropped_filters"):
        print("Dropped:", query_info["dropped_filters"][:3])
    if query_info.get("reassigned_filters"):
        print("Reassigned:", query_info["reassigned_filters"][:3])

    # 3) embed query
    qvec = embedder.encode(user_text, normalize_embeddings=True).tolist()

    # 4) Build study filter only if HARD_FILTER
    study_filter = None
    if strategy == "HARD_FILTER" and filters:
        study_filter = Filter(
            must=[
                FieldCondition(key=f, match=MatchValue(value=v))
                for f, v in filters.items()
            ]
        )

    # 5) retrieve STUDY (first pass)
    # If low confidence, increase recall a bit
    effective_topk_study = top_k_study
    if float(conf.get("overall_confidence", 0.0)) < 0.60:
        effective_topk_study = max(top_k_study, 25)

    study_hits = hybrid_search_collection(
        client=qdrant_client,
        collection=study_collection,
        query_text=user_text,
        query_vector=qvec,
        bm25_index=bm25_study,
        top_k=effective_topk_study,
        qdrant_filter=study_filter
    )

    # If SOFT_BOOST, boost based on metadata matches (no filtering)
    if strategy == "SOFT_BOOST" and filters:
        study_hits = _apply_soft_boost(study_hits, filters, per_match_bonus=0.03)

    # Gate by similarity threshold
    gated_study = [h for h in study_hits if h["vector_score"] >= sim_threshold]

    # 6) Relaxation ladder if HARD_FILTER collapses
    if strategy == "HARD_FILTER" and len(gated_study) == 0:
        # Relax to SOFT_BOOST: rerun without filter, then boost
        print("Relaxation: HARD_FILTER → SOFT_BOOST")
        study_hits = hybrid_search_collection(
            client=qdrant_client,
            collection=study_collection,
            query_text=user_text,
            query_vector=qvec,
            bm25_index=bm25_study,
            top_k=effective_topk_study,
            qdrant_filter=None
        )
        if filters:
            study_hits = _apply_soft_boost(study_hits, filters, per_match_bonus=0.03)
        gated_study = [h for h in study_hits if h["vector_score"] >= sim_threshold]

    if len(gated_study) == 0:
        # Final fallback: semantic only with higher recall
        print("Relaxation: → SEMANTIC_ONLY fallback")
        study_hits = hybrid_search_collection(
            client=qdrant_client,
            collection=study_collection,
            query_text=user_text,
            query_vector=qvec,
            bm25_index=bm25_study,
            top_k=max(effective_topk_study, 35),
            qdrant_filter=None
        )
        gated_study = [h for h in study_hits if h["vector_score"] >= sim_threshold]

    study_hits = gated_study

    # 7) Derive top GSE IDs
    top_gse_ids = []
    for h in study_hits:
        gse = (h.get("payload") or {}).get("gse_id")
        if gse and gse not in top_gse_ids:
            top_gse_ids.append(gse)
    top_gse_ids = top_gse_ids[:10]

    # 8) SAMPLE retrieval restricted by top_gse_ids
    sample_filter = None
    if top_gse_ids:
        sample_filter = Filter(
            must=[FieldCondition(key="gse_id", match=MatchAny(any=top_gse_ids))]
        )

    sample_hits = hybrid_search_collection(
        client=qdrant_client,
        collection=sample_collection,
        query_text=user_text,
        query_vector=qvec,
        bm25_index=bm25_sample,
        top_k=top_k_sample,
        qdrant_filter=sample_filter
    )

    # Soft boost samples too (optional, same filters)
    if strategy in ("SOFT_BOOST", "HARD_FILTER") and filters:
        sample_hits = _apply_soft_boost(sample_hits, filters, per_match_bonus=0.02)

    sample_hits = [h for h in sample_hits if h["vector_score"] >= sim_threshold]

    # 9) pack
    def pack(hit: dict, source: str) -> dict:
        p = hit.get("payload") or {}
        return {
            "source": source,
            "final_score": float(hit.get("final_score", 0.0)),
            "vector_score": float(hit.get("vector_score", 0.0)),
            "gse_id": p.get("gse_id"),
            "gsm_id": p.get("gsm_id"),
            "field": p.get("field"),
            "organism": _payload_get(p, "organism"),
            "assay_type": _payload_get(p, "assay_type"),
            "tissue": _payload_get(p, "tissue"),
            "library_strategy": _payload_get(p, "library_strategy"),
            "library_source": _payload_get(p, "library_source"),
            "library_selection": _payload_get(p, "library_selection"),
            "molecule": _payload_get(p, "molecule"),    
            "genotype": _payload_get(p, "genotype"),
            "cell_line": _payload_get(p, "cell_line"),
            "cell_type": _payload_get(p, "cell_type"),
            "bioproject_url": _payload_get(p, "bioproject_url"),
            "biosample_url": _payload_get(p, "biosample_url"),
            "sra_url": _payload_get(p, "sra_url"),
            "text": (p.get("text") or "")[:1200],
        }

    retrieved_context = [pack(h, "study") for h in study_hits] + [pack(h, "sample") for h in sample_hits]
    
    sample_context = build_sample_context(
        qdrant_client,
        retrieved_context,
        sample_collection
    )

    return {
        "retrieved_context": retrieved_context,
        "sample_context": sample_context,
        "top_gse_ids": top_gse_ids
    }

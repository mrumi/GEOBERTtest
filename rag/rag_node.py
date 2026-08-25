# ============================================================
# rag/rag_node.py — RAG Node (Full Pipeline Orchestrator)
# ============================================================


import math
from typing import Optional
from qdrant_client.models import Filter, FieldCondition, MatchValue

from rag.hybrid_search import (
    hybrid_search_collection,
    apply_boosts,
    build_qdrant_filter,
    prune_invalid_filters,
)


def sigmoid(x: float) -> float:
    """Map a raw cross-encoder logit to (0, 1) for human-readable display."""
    try:
        return 1.0 / (1.0 + math.exp(-x))
    except OverflowError:
        return 0.0 if x < 0 else 1.0


# ============================================================
# Neighbor Chunk Fetcher
# ============================================================

def fetch_neighbor_chunks(
    parent_id   : str,
    child_index : int,
    collection  : str,
    qdrant_client,
    window      : int,
) -> list[dict]:
    """Fetch neighboring child chunks around a retrieved chunk."""

    if window <= 0:
        return []

    neighbor_indexes = list(range(max(0, child_index - window), child_index + window + 1))
    neighbor_indexes = [idx for idx in neighbor_indexes if idx != child_index]

    if not neighbor_indexes:
        return []

    neighbor_chunks = []

    for neighbor_index in neighbor_indexes:
        neighbor_results = qdrant_client.scroll(
            collection_name = collection,
            scroll_filter   = Filter(
                must=[
                    FieldCondition(key="parent_id",   match=MatchValue(value=parent_id)),
                    FieldCondition(key="child_index", match=MatchValue(value=neighbor_index)),
                ]
            ),
            limit        = 1,
            with_payload = True,
            with_vectors = False
        )
        points = neighbor_results[0]
        if points:
            neighbor_chunks.append(points[0].payload)

    neighbor_chunks.sort(key=lambda p: p.get("child_index", 0))
    return neighbor_chunks


# ============================================================
# Parent-Child Aggregation
# ============================================================

def aggregate_children_by_parent(
    reranked_children     : list[dict],
    study_collection      : str,
    semantic_focus_fields : list[str],
    qdrant_client,
    neighbor_window        : int,
) -> list[dict]:
    """Group reranked child chunks by GSE study and build structured evidence blocks."""

    if not reranked_children:
        return []

    gse_children_map = {}
    for child in reranked_children:
        payload = child.get("payload", {}) or {}
        gse_id  = payload.get("gse_id", "")
        if not gse_id:
            continue
        gse_children_map.setdefault(gse_id, []).append(child)

    aggregated_studies = []

    for gse_id, children in gse_children_map.items():

        children.sort(key=lambda c: c.get("cross_encoder_score", 0.0), reverse=True)

        top_score   = children[0].get("cross_encoder_score", 0.0)
        top_payload = children[0].get("payload", {}) or {}

        study_metadata = {
            "organism"         : top_payload.get("organism",         ""),
            "tissue"           : top_payload.get("tissue",           ""),
            "assay_type"       : top_payload.get("assay_type",       ""),
            "library_strategy" : top_payload.get("library_strategy", ""),
            "library_source"   : top_payload.get("library_source",   ""),
            "instrument_model" : top_payload.get("instrument_model", ""),
            "bioproject_url"   : top_payload.get("bioproject_url",   ""),
            # Series relationships — stored as "true"/"false" strings
            # in Qdrant payload (see indexing/document_parser.py),
            # converted back to real bools here for API consumers.
            "is_superseries"   : str(top_payload.get("is_superseries", "false")).lower() == "true",
            "is_subseries"     : str(top_payload.get("is_subseries",   "false")).lower() == "true",
            "parent_series_id" : top_payload.get("parent_series_id", ""),
            "subseries_ids"    : top_payload.get("subseries_ids",    []) or [],
        }

        best_child_per_field = {}
        for child in children:
            payload     = child.get("payload", {}) or {}
            field_name  = payload.get("field", "unknown")
            child_score = child.get("cross_encoder_score", 0.0)
            if field_name not in best_child_per_field:
                best_child_per_field[field_name] = child
            elif child_score > best_child_per_field[field_name].get("cross_encoder_score", 0.0):
                best_child_per_field[field_name] = child

        field_texts = {}
        for field_name, best_child in best_child_per_field.items():

            payload     = best_child.get("payload", {}) or {}
            parent_id   = payload.get("parent_id", "")
            child_index = payload.get("child_index", 0)
            core_text   = payload.get("text", "")

            if neighbor_window > 0 and parent_id:
                neighbors = fetch_neighbor_chunks(
                    parent_id=parent_id, child_index=child_index,
                    collection=study_collection, qdrant_client=qdrant_client,
                    window=neighbor_window
                )
                if neighbors:
                    all_texts = []
                    for neighbor in neighbors:
                        if neighbor.get("child_index", 0) < child_index:
                            all_texts.append(neighbor.get("text", ""))
                    all_texts.append(core_text)
                    for neighbor in neighbors:
                        if neighbor.get("child_index", 0) > child_index:
                            all_texts.append(neighbor.get("text", ""))
                    field_texts[field_name] = " ".join(t for t in all_texts if t)
                else:
                    field_texts[field_name] = core_text
            else:
                field_texts[field_name] = core_text

        aggregated_studies.append({
            "gse_id"          : gse_id,
            "top_score"       : top_score,
            "relevance_score" : sigmoid(top_score),
            "fields"          : field_texts,
            "metadata"        : study_metadata,
        })

    aggregated_studies.sort(key=lambda s: s["top_score"], reverse=True)
    return aggregated_studies


# ============================================================
# RAG Node — Main Orchestrator
# ============================================================

def rag_node(
    state              : dict,
    qdrant_client,
    groq_client,
    dense_embedder,
    cross_encoder,
    generate_sparse_vector_fn,
    organism_resolver,
    settings,
) -> dict:
    """
    Full RAG pipeline orchestrator.

    Args:
        state                     : Current GeoState dict.
        qdrant_client              : QdrantClient.
        groq_client                 : Groq client.
        dense_embedder              : SentenceTransformer.
        cross_encoder               : CrossEncoder.
        generate_sparse_vector_fn   : Callable(text) -> SparseVector.
        organism_resolver           : OrganismResolver instance.
        settings                    : core.config.Settings instance
                                      (provides all TOP_K_*, SIM_THRESHOLD,
                                      ALPHA_*, boost values, collection
                                      names, GROQ_QUERY_MODEL, NEIGHBOR_WINDOW).

    Returns:
        Dict with updated state fields (see GeoState schema).
    """

    from rag.query_understanding import analyze_query

    # ── Step 1: Extract last user message ──────────────────
    user_query = ""
    for message in reversed(state["messages"]):
        message_type = getattr(message, "type", None)
        class_name   = message.__class__.__name__
        if message_type == "human" or class_name == "HumanMessage":
            user_query = message.content
            break

    if not user_query:
        print("  [rag_node] No user message found in state.")
        return {
            "query_info": {}, "retrieved_context": [], "reranked_context": [],
            "sample_context": [], "top_gse_ids": [], "dropped_filters": {},
        }

    print(f"\n{'='*60}\nRAG Node — Query: {user_query[:80]}\n{'='*60}")

    # ── Step 2: LLM Query Understanding ────────────────────
    query_info = analyze_query(
        query             = user_query,
        groq_client       = groq_client,
        organism_resolver = organism_resolver,
        groq_query_model  = settings.GROQ_QUERY_MODEL,
        session_memory    = state.get("session_memory", []),
    )

    print(f"Intent: {query_info['intent']} | Strategy: {query_info['strategy']} | Filters: {query_info['filters']}")

    # ── Step 3: Generate query vectors ─────────────────────
    dense_query_vector  = dense_embedder.encode(user_query, normalize_embeddings=True).tolist()
    sparse_query_vector = generate_sparse_vector_fn(user_query)

    # ── Step 4: Build Qdrant filter (study side) ───────────
    study_qdrant_filter = None
    dropped_filters      = {}

    if query_info["strategy"] == "HARD_FILTER" and query_info["filters"]:

        validated_study_filters = prune_invalid_filters(
            filters=query_info["filters"], collection_name=settings.STUDY_COLLECTION,
            qdrant_client=qdrant_client,
        )
        dropped_filters = {
            field: value for field, value in query_info["filters"].items()
            if field not in validated_study_filters
        }
        if validated_study_filters:
            study_qdrant_filter = build_qdrant_filter(
                filters=validated_study_filters, logical_operator=query_info["logical_operator"]
            )

    # ── Step 5: Hybrid study retrieval ─────────────────────
    study_hits = hybrid_search_collection(
        collection_name     = settings.STUDY_COLLECTION,
        query_text          = user_query,
        query_dense_vector  = dense_query_vector,
        query_sparse_vector = sparse_query_vector,
        top_k               = settings.TOP_K_STUDY_RETRIEVAL,
        qdrant_client       = qdrant_client,
        alpha_dense         = settings.ALPHA_DENSE,
        alpha_sparse        = settings.ALPHA_SPARSE,
        qdrant_filter       = study_qdrant_filter,
    )

    # ── Step 6: Apply boosts ───────────────────────────────
    study_hits = apply_boosts(
        hits=study_hits, resolved_organism=query_info.get("resolved_organism"),
        semantic_focus_fields=query_info["semantic_focus_fields"], filters=query_info["filters"],
        exact_payload_match_boost=settings.EXACT_PAYLOAD_MATCH_BOOST,
        field_match_boost=settings.FIELD_MATCH_BOOST,
        field_focus_boost=settings.FIELD_FOCUS_BOOST,
    )

    # ── Step 7: Gate by similarity threshold ───────────────
    study_hits = [hit for hit in study_hits if hit["dense_score"] >= settings.SIM_THRESHOLD]

    # ── Step 8: Cross-encoder reranking (study side) ───────
    if study_hits:
        rerank_pairs = [(user_query, hit["payload"].get("text", "")) for hit in study_hits]
        cross_encoder_scores = cross_encoder.predict(rerank_pairs)
        for hit, score in zip(study_hits, cross_encoder_scores):
            hit["cross_encoder_score"] = float(score)
        study_hits.sort(key=lambda h: h["cross_encoder_score"], reverse=True)
        study_hits = study_hits[:settings.TOP_K_AFTER_RERANK]

    # ── Step 9: Parent-child aggregation ───────────────────
    reranked_context = aggregate_children_by_parent(
        reranked_children=study_hits, study_collection=settings.STUDY_COLLECTION,
        semantic_focus_fields=query_info["semantic_focus_fields"],
        qdrant_client=qdrant_client, neighbor_window=settings.NEIGHBOR_WINDOW,
    )

    top_gse_ids = [study["gse_id"] for study in reranked_context]

    # ── Step 10: Sample retrieval — INDEPENDENT of study ───
    sample_qdrant_filter   = None
    sample_dropped_filters = {}

    if query_info["strategy"] == "HARD_FILTER" and query_info["filters"]:

        validated_sample_filters = prune_invalid_filters(
            filters=query_info["filters"], collection_name=settings.SAMPLE_COLLECTION,
            qdrant_client=qdrant_client,
        )
        sample_dropped_filters = {
            field: value for field, value in query_info["filters"].items()
            if field not in validated_sample_filters
        }
        if validated_sample_filters:
            sample_qdrant_filter = build_qdrant_filter(
                filters=validated_sample_filters, logical_operator=query_info["logical_operator"]
            )

    sample_hits = hybrid_search_collection(
        collection_name     = settings.SAMPLE_COLLECTION,
        query_text          = user_query,
        query_dense_vector  = dense_query_vector,
        query_sparse_vector = sparse_query_vector,
        top_k               = settings.TOP_K_SAMPLE_RETRIEVAL,
        qdrant_client       = qdrant_client,
        alpha_dense         = settings.ALPHA_DENSE,
        alpha_sparse        = settings.ALPHA_SPARSE,
        qdrant_filter       = sample_qdrant_filter,
    )

    sample_hits = apply_boosts(
        hits=sample_hits, resolved_organism=query_info.get("resolved_organism"),
        semantic_focus_fields=[], filters=query_info["filters"],
        exact_payload_match_boost=settings.EXACT_PAYLOAD_MATCH_BOOST,
        field_match_boost=settings.FIELD_MATCH_BOOST,
        field_focus_boost=settings.FIELD_FOCUS_BOOST,
    )

    sample_hits = [hit for hit in sample_hits if hit["dense_score"] >= settings.SIM_THRESHOLD]

    # ── Step 10.5: Cross-encoder reranking (sample side) ────
    
    if sample_hits:
        sample_rerank_pairs = [(user_query, hit["payload"].get("text", "")) for hit in sample_hits]
        sample_cross_scores = cross_encoder.predict(sample_rerank_pairs)
        for hit, score in zip(sample_hits, sample_cross_scores):
            hit["cross_encoder_score"] = float(score)
            hit["relevance_score"] = sigmoid(float(score))
        sample_hits.sort(key=lambda h: h["cross_encoder_score"], reverse=True)
        sample_hits = sample_hits[:settings.TOP_K_SAMPLE_AFTER_RERANK]


    for field, value in sample_dropped_filters.items():
        dropped_filters.setdefault(field, value)

    # ── Step 11: Pack raw retrieved context (logging) ──────
    retrieved_context = []

    for hit in study_hits:
        payload = hit.get("payload", {}) or {}
        retrieved_context.append({
            "source": "study", "gse_id": payload.get("gse_id", ""), "gsm_id": "",
            "field": payload.get("field", ""), "parent_id": payload.get("parent_id", ""),
            "child_index": payload.get("child_index", 0), "organism": payload.get("organism", ""),
            "tissue": payload.get("tissue", ""), "assay_type": payload.get("assay_type", ""),
            "library_strategy": payload.get("library_strategy", ""),
            "bioproject_url": payload.get("bioproject_url", ""),
            "dense_score": hit.get("dense_score", 0.0), "sparse_score": hit.get("sparse_score", 0.0),
            "final_score": hit.get("final_score", 0.0),
            "cross_encoder_score": hit.get("cross_encoder_score", 0.0),
            "boost_breakdown": hit.get("boost_breakdown", {}),
            "text": payload.get("text", "")[:300],
        })

    for hit in sample_hits:
        payload = hit.get("payload", {}) or {}
        retrieved_context.append({
            "source": "sample", "gse_id": payload.get("gse_id", ""), "gsm_id": payload.get("gsm_id", ""),
            "field": "", "parent_id": payload.get("parent_id", ""), "child_index": 0,
            "organism": payload.get("organism", ""), "tissue": payload.get("tissue", ""),
            "assay_type": payload.get("assay_type", ""),
            "library_strategy": payload.get("library_strategy", ""),
            "bioproject_url": "", "biosample_url": payload.get("biosample_url", ""),
            "sra_url": payload.get("sra_url", ""),
            "dense_score": hit.get("dense_score", 0.0), "sparse_score": hit.get("sparse_score", 0.0),
            "final_score": hit.get("final_score", 0.0),
            "cross_encoder_score": hit.get("cross_encoder_score", 0.0),
            "boost_breakdown": hit.get("boost_breakdown", {}),
            "text": payload.get("text", "")[:300],
        })

    return {
        "query_info"       : query_info,
        "retrieved_context": retrieved_context,
        "reranked_context" : reranked_context,
        "sample_context"   : sample_hits,
        "top_gse_ids"      : top_gse_ids,
        "dropped_filters"  : dropped_filters,
    }
# ============================================================
# rag/hybrid_search.py — Hybrid Search (Dense + Sparse)
# ============================================================

import math
from typing import Optional
from qdrant_client.models import Filter, FieldCondition, MatchText


# ============================================================
# Score Normalization
# ============================================================

def normalize_scores_minmax(scores: list[float]) -> list[float]:
    """Normalize a list of scores to [0, 1] using min-max scaling."""
    if not scores:
        return []

    min_score = min(scores)
    max_score = max(scores)

    if math.isclose(min_score, max_score):
        return [0.5] * len(scores)

    return [(score - min_score) / (max_score - min_score) for score in scores]


# ============================================================
# Qdrant Filter Builder
# ============================================================

def build_qdrant_filter(filters: dict, logical_operator: str) -> Optional[Filter]:
    """
    Build a Qdrant Filter object using MatchText (case-insensitive,
    token-level "contains all words" matching).
    """
    if not filters:
        return None

    conditions = [
        FieldCondition(key=field, match=MatchText(text=str(value)))
        for field, value in filters.items()
        if value and str(value).strip()
    ]

    if not conditions:
        return None

    if logical_operator == "OR":
        return Filter(should=conditions)
    if logical_operator == "NOT":
        return Filter(must_not=conditions)

    return Filter(must=conditions)


# ============================================================
# Per-Field Filter Pruning
# ============================================================

def prune_invalid_filters(
    filters         : dict,
    collection_name : str,
    qdrant_client,
) -> dict:
    """
    Test each filter field individually via a cheap count() call.
    Drops fields that match zero points on their own, keeping
    the rest — fixes the "one bad field drags down valid ones"
    problem the blunt all-or-nothing fallback used to cause.

    Args:
        filters         : Dict of field -> value pairs.
        collection_name : Qdrant collection to validate against.
        qdrant_client   : QdrantClient instance.
    """
    if not filters:
        return {}

    valid_filters = {}

    for field, value in filters.items():

        if not value or not str(value).strip():
            continue

        single_field_filter = Filter(
            must=[FieldCondition(key=field, match=MatchText(text=str(value)))]
        )

        try:
            count_result = qdrant_client.count(
                collection_name = collection_name,
                count_filter    = single_field_filter,
                exact           = False,
            )
            match_count = count_result.count
        except Exception as error:
            print(f"  [filter validation error] '{field}': {error} — dropping this field")
            continue

        if match_count > 0:
            valid_filters[field] = value
        else:
            print(
                f"  [filter pruned] '{field}': '{value}' matched 0 points "
                f"individually — dropping only this field, keeping the rest"
            )

    return valid_filters


def get_payload_value(payload: dict, field: str) -> Optional[str]:
    """Safely extract a value from a Qdrant point payload."""
    if not payload:
        return None

    value = payload.get(field)
    if value not in (None, "", []):
        return str(value)

    nested_metadata = payload.get("metadata")
    if isinstance(nested_metadata, dict):
        value = nested_metadata.get(field)
        if value not in (None, "", []):
            return str(value)

    return None


def _text_values_match(filter_value: str, payload_value: str) -> bool:
    """Loose token-overlap check mirroring MatchText semantics."""
    filter_tokens  = set(filter_value.lower().split())
    payload_tokens = set(payload_value.lower().split())
    return filter_tokens.issubset(payload_tokens)


# ============================================================
# Post-Retrieval Boost Application
# ============================================================

def apply_boosts(
    hits                       : list[dict],
    resolved_organism          : Optional[dict],
    semantic_focus_fields      : list[str],
    filters                    : Optional[dict],
    exact_payload_match_boost  : float,
    field_match_boost          : float,
    field_focus_boost          : float,
) -> list[dict]:
    """
    Apply score boosts to retrieved chunks after hybrid merge.

    Boost values are passed explicitly (settings.EXACT_PAYLOAD_MATCH_BOOST,
    settings.FIELD_MATCH_BOOST, settings.FIELD_FOCUS_BOOST) rather
    than referenced as globals.
    """
    if not hits:
        return hits

    canonical_organism = None
    if resolved_organism and resolved_organism.get("source") != "unresolved":
        canonical_organism = resolved_organism.get("canonical_name", "").lower()

    filters = filters or {}

    for hit in hits:

        payload = hit.get("payload", {}) or {}
        boost_breakdown = {}

        if canonical_organism:
            chunk_organism = get_payload_value(payload, "organism")
            if chunk_organism and chunk_organism.lower() == canonical_organism:
                boost_breakdown["organism"] = exact_payload_match_boost

        for field, value in filters.items():
            if field == "organism" or not value:
                continue
            chunk_value = get_payload_value(payload, field)
            if chunk_value and _text_values_match(str(value), chunk_value):
                boost_breakdown[field] = field_match_boost

        if semantic_focus_fields:
            chunk_field = payload.get("field", "")
            if chunk_field and chunk_field in semantic_focus_fields:
                boost_breakdown["focus_field"] = field_focus_boost

        hit["boost_breakdown"] = boost_breakdown
        hit["final_score"] = float(hit.get("final_score", 0.0)) + sum(boost_breakdown.values())

    hits.sort(key=lambda h: h["final_score"], reverse=True)

    return hits


# ============================================================
# Core Hybrid Search Function
# ============================================================

def hybrid_search_collection(
    collection_name       : str,
    query_text            : str,
    query_dense_vector    : list[float],
    query_sparse_vector,
    top_k                 : int,
    qdrant_client,
    alpha_dense           : float,
    alpha_sparse          : float,
    qdrant_filter         : Optional[Filter] = None,
) -> list[dict]:
    """
    Perform hybrid search on a Qdrant collection using both
    dense and sparse vectors.

    alpha_dense/alpha_sparse are passed explicitly
    (settings.ALPHA_DENSE / settings.ALPHA_SPARSE).
    """

    dense_results = qdrant_client.query_points(
        collection_name = collection_name,
        query           = query_dense_vector,
        using           = "dense",
        query_filter    = qdrant_filter,
        limit           = top_k,
        with_payload    = True
    ).points

    filter_dropped = False

    if qdrant_filter is not None and len(dense_results) == 0:
        print(
            f"  [filter fallback] '{query_text}': hard filter matched 0 "
            f"results in dense search — retrying without filter"
        )
        dense_results = qdrant_client.query_points(
            collection_name = collection_name,
            query           = query_dense_vector,
            using           = "dense",
            query_filter    = None,
            limit           = top_k,
            with_payload    = True
        ).points
        filter_dropped = True

    dense_score_map = {str(point.id): float(point.score) for point in dense_results}
    payload_map      = {str(point.id): point.payload for point in dense_results}

    sparse_results = qdrant_client.query_points(
        collection_name = collection_name,
        query           = query_sparse_vector,
        using           = "sparse",
        limit           = top_k,
        with_payload    = True
    ).points

    sparse_score_map = {str(point.id): float(point.score) for point in sparse_results}

    for point in sparse_results:
        point_id = str(point.id)
        if point_id not in payload_map:
            payload_map[point_id] = point.payload

    all_point_ids = list(set(dense_score_map.keys()) | set(sparse_score_map.keys()))

    if not all_point_ids:
        return []

    dense_scores  = [dense_score_map.get(pid,  0.0) for pid in all_point_ids]
    sparse_scores = [sparse_score_map.get(pid, 0.0) for pid in all_point_ids]

    if dense_scores and max(dense_scores) == 0.0:
        print(
            f"  [warning] '{query_text}': all dense scores are 0 — "
            f"dense search returned nothing usable, relying on sparse only"
        )

    dense_scores_normalized  = normalize_scores_minmax(dense_scores)
    sparse_scores_normalized = normalize_scores_minmax(sparse_scores)

    results = []

    for index, point_id in enumerate(all_point_ids):

        dense_norm  = dense_scores_normalized[index]
        sparse_norm = sparse_scores_normalized[index]

        final_score = (alpha_dense * dense_norm) + (alpha_sparse * sparse_norm)

        results.append({
            "id"             : point_id,
            "final_score"    : float(final_score),
            "dense_score"    : dense_score_map.get(point_id,  0.0),
            "sparse_score"   : sparse_score_map.get(point_id, 0.0),
            "dense_norm"     : dense_norm,
            "sparse_norm"    : sparse_norm,
            "payload"        : payload_map.get(point_id, {}),
            "filter_dropped" : filter_dropped,
        })

    results.sort(key=lambda r: r["final_score"], reverse=True)

    return results[:top_k]
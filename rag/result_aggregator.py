# ============================================================
# rag/result_aggregator.py — Dashboard Stats Aggregator
# ============================================================
# Builds the summary stats
# shown in the frontend dashboard (top stat bar + "Stats &
# Quality" panel), computed ONLY from fields our pipeline
# actually produces.
#
# WHAT'S KEPT (all backed by real pipeline output):
#   - Dataset / Sample / Platform / Tissue counts
#   - Platform (library_strategy) distribution with percentages
#   - Query Match — average relevance_score (sigmoid-normalized,
#     already 0-1) across returned studies
#   - Metadata Match — fraction of extracted filters that
#     survived per-field pruning (i.e. weren't in dropped_filters)
#   - Top Fields Matched — most common study fields present
#     across the returned results (title, study_summary, etc.)
# ============================================================

from collections import Counter
from typing import Optional


def _get_gse_library_strategy_map(
    reranked_context : list[dict],
    sample_context   : list[dict],
) -> dict[str, str]:
    """
    Build a {gse_id: library_strategy} map covering every distinct
    study represented in EITHER the study-level or sample-level
    results — a study whose title/summary didn't rank well but
    whose samples matched (see rag_node's independent sample
    retrieval) would otherwise be invisible to platform counting.

    Study-level metadata is preferred when available (more
    likely to be populated); falls back to the first sample's
    library_strategy for GSEs only present in sample_context.
    """
    gse_to_strategy: dict[str, str] = {}

    for study in reranked_context:
        gse_id = study.get("gse_id", "")
        strategy = study.get("metadata", {}).get("library_strategy", "")
        if gse_id and strategy:
            gse_to_strategy[gse_id] = strategy

    for hit in sample_context:
        payload = hit.get("payload", {}) or {}
        gse_id   = payload.get("gse_id", "")
        strategy = payload.get("library_strategy", "")
        if gse_id and gse_id not in gse_to_strategy and strategy:
            gse_to_strategy[gse_id] = strategy

    return gse_to_strategy


def compute_stats_overview(
    reranked_context : list[dict],
    sample_context   : list[dict],
) -> dict:
    """
    Top stat bar: Datasets / Samples / Platforms / Tissues counts,
    plus a platform (library_strategy) distribution breakdown.

    Returns:
        {
            "dataset_count": int,
            "sample_count": int,
            "platform_count": int,
            "tissue_count": int,
            "platform_distribution": [
                {"name": "RNA-Seq", "count": 10, "percent": 83.3},
                ...
            ],
        }
    """

    # Distinct GSE IDs across BOTH study and sample results —
    # a study only found via its samples still counts as a
    # returned dataset.
    all_gse_ids = {s.get("gse_id", "") for s in reranked_context if s.get("gse_id")}
    all_gse_ids |= {
        hit.get("payload", {}).get("gse_id", "")
        for hit in sample_context
        if hit.get("payload", {}).get("gse_id")
    }

    dataset_count = len(all_gse_ids)
    sample_count  = len(sample_context)

    gse_to_strategy = _get_gse_library_strategy_map(reranked_context, sample_context)
    strategy_counter = Counter(gse_to_strategy.values())
    platform_count = len(strategy_counter)

    total_with_strategy = sum(strategy_counter.values())
    platform_distribution = [
        {
            "name"    : strategy,
            "count"   : count,
            "percent" : round(count / total_with_strategy * 100, 1) if total_with_strategy else 0.0,
        }
        for strategy, count in strategy_counter.most_common()
    ]

    # Unique tissue values — union of study-level metadata AND
    # sample-level payloads, deduplicated case-insensitively
    
    tissue_values_normalized: dict[str, str] = {}  # lowercase -> original casing (first seen)

    for study in reranked_context:
        tissue = study.get("metadata", {}).get("tissue", "")
        if tissue:
            key = tissue.strip().lower()
            tissue_values_normalized.setdefault(key, tissue.strip())

    for hit in sample_context:
        tissue = hit.get("payload", {}).get("tissue", "")
        if tissue:
            key = tissue.strip().lower()
            tissue_values_normalized.setdefault(key, tissue.strip())

    tissue_count = len(tissue_values_normalized)

    return {
        "dataset_count"         : dataset_count,
        "sample_count"          : sample_count,
        "platform_count"        : platform_count,
        "tissue_count"          : tissue_count,
        "platform_distribution" : platform_distribution,
    }


def compute_relevance_quality(
    reranked_context : list[dict],
    sample_context   : list[dict],
    query_info       : dict,
    dropped_filters  : dict,
) -> dict:
    """
    "Relevance & Quality" panel — Query Match and Metadata Match
    only. Coverage/Completeness deliberately omitted (see module
    docstring).  Query Match now averages BOTH study and sample relevance
    scores — both come from the same cross_encoder instance via
    sigmoid() (see rag_node.py), so they're on one consistent
    scale and safe to average together.

    Returns:
        {
            "query_match"    : float | None,   # 0-1, avg relevance_score
            "metadata_match" : float | None,   # 0-1, fraction of filters that survived
        }
        None when there's nothing to compute from (e.g. no
        results, or no filters were extracted at all) — the
        frontend should render these as "N/A", not "0%", since
        0% would misleadingly imply a bad match rather than
        "not applicable".
    """
    study_scores  = [s.get("relevance_score", 0.0) for s in reranked_context]
    sample_scores = [
        h["relevance_score"] for h in sample_context
        if h.get("relevance_score") is not None
    ]
    all_scores = study_scores + sample_scores

    query_match = None
    if all_scores:
        query_match = round(sum(all_scores) / len(all_scores), 4)

    metadata_match = None
    total_filters = len(query_info.get("filters", {}))
    if total_filters > 0:
        dropped_count = len(dropped_filters or {})
        metadata_match = round((total_filters - dropped_count) / total_filters, 4)

    return {
        "query_match"    : query_match,
        "metadata_match" : metadata_match,
    }


def compute_top_fields_matched(
    reranked_context : list[dict],
    top_n            : int = 5,
) -> list[str]:
    """
    Most common study fields (title, study_summary, overall_design,
    etc.) present across the returned results — backs the "Top
    Fields Matched" badge list.

    Returns:
        List of field names, most frequent first, e.g.
        ["title", "study_summary", "overall_design"].
    """
    field_counter = Counter()

    for study in reranked_context:
        for field_name in study.get("fields", {}).keys():
            field_counter[field_name] += 1

    return [field for field, _ in field_counter.most_common(top_n)]


def build_dashboard_stats(
    reranked_context : list[dict],
    sample_context   : list[dict],
    query_info       : dict,
    dropped_filters  : Optional[dict] = None,
) -> dict:
    """
    Single entry point — combines all three sections into one
    dict, ready to attach to the query response for the frontend.

    Returns:
        {
            "stats_overview"     : {...},   # see compute_stats_overview
            "relevance_quality"  : {...},   # see compute_relevance_quality
            "top_fields_matched" : [...],   # see compute_top_fields_matched
        }
    """
    return {
        "stats_overview"     : compute_stats_overview(reranked_context, sample_context),
        "relevance_quality"  : compute_relevance_quality(
            reranked_context, sample_context, query_info, dropped_filters or {}
        ),
        "top_fields_matched" : compute_top_fields_matched(reranked_context),
    }

from collections import defaultdict
from typing import List, Dict, Any

from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue


def expand_samples_from_studies(
    qdrant_client,
    study_ids,
    sample_collection,
    max_samples_per_study=200
):
    """
    Retrieve ALL samples belonging to retrieved studies.
    """

    expanded_samples = []

    for gse in study_ids:

        offset = None
        collected = 0

        while True:

            points, offset = qdrant_client.scroll(
                collection_name=sample_collection,
                scroll_filter=Filter(
                    must=[
                        FieldCondition(
                            key="gse_id",
                            match=MatchValue(value=gse)
                        )
                    ]
                ),
                limit=64,
                offset=offset,
                with_payload=True,
                with_vectors=False
            )

            for pt in points:

                payload = pt.payload or {}
                expanded_samples.append(payload)
                collected += 1

                if collected >= max_samples_per_study:
                    break

            if offset is None or collected >= max_samples_per_study:
                break

    return expanded_samples


def compress_samples_by_condition(samples):
    """
    Compress replicate samples when sample count is large.
    """

    groups = defaultdict(list)

    for s in samples:

        condition = (
            s.get("genotype")
            or s.get("treatment")
            or s.get("condition")
            or s.get("title")
            or "unknown"
        )

        groups[condition].append(s)

    compressed = []

    for cond, items in groups.items():

        compressed.append({
            "condition": cond,
            "replicates": len(items),
            "sample_ids": [x.get("gsm_id") for x in items],
            "tissue": items[0].get("tissue"),
            "cell_line": items[0].get("cell_line"),
            "cell_type": items[0].get("cell_type"),
            "genotype": items[0].get("genotype")
        })

    return compressed


def build_sample_context(
    qdrant_client,
    retrieved_context,
    sample_collection,
    compression_threshold=12
):
    """
    Hybrid strategy:

    ≤20 samples → send full GSM metadata
    >20 samples → compress into condition groups
    """

    study_ids = list({
        item.get("gse_id")
        for item in retrieved_context
        if item.get("gse_id")
    })

    if not study_ids:
        return []

    expanded_samples = expand_samples_from_studies(
        qdrant_client,
        study_ids,
        sample_collection
    )

    # group samples per study
    study_map = defaultdict(list)

    for s in expanded_samples:
        gse = s.get("gse_id")
        if gse:
            study_map[gse].append(s)

    final_context = []

    for gse_id, samples in study_map.items():

        if len(samples) <= compression_threshold:

            # send full GSM metadata
            final_context.append({
                "gse_id": gse_id,
                "sample_count": len(samples),
                "mode": "full_samples",
                "samples": [
                    {
                        "gsm_id": s.get("gsm_id"),
                        "title": s.get("title"),
                        "tissue": s.get("tissue"),
                        "genotype": s.get("genotype"),
                        "cell_line": s.get("cell_line"),
                        "cell_type": s.get("cell_type")
                    }
                    for s in samples
                ]
            })

        else:

            # compress large studies
            compressed = compress_samples_by_condition(samples)

            final_context.append({
                "gse_id": gse_id,
                "sample_count": len(samples),
                "mode": "compressed_conditions",
                "conditions": compressed
            })

    return final_context

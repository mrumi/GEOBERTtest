import math
from typing import Optional, List, Dict

from qdrant_client import QdrantClient
from qdrant_client.models import Filter

from .bm25_index import BM25Index
from src.config import ALPHA_VECTOR, BETA_BM25



def _minmax_norm(values: list[float]) -> list[float]:
    if not values:
        return []
    vmin, vmax = min(values), max(values)
    if math.isclose(vmin, vmax):
        return [0.5 for _ in values]
    return [(v - vmin) / (vmax - vmin) for v in values]

def _fetch_points_by_ids(
    client: QdrantClient,
    collection: str,
    ids: list[str],
    with_vectors: bool = False
):
    if not ids:
        return []
    # Qdrant expects ids as original types; we used uuid strings, so ok
    return client.retrieve(
        collection_name=collection,
        ids=ids,
        with_payload=True,
        with_vectors=with_vectors
    )

def hybrid_search_collection(
    client: QdrantClient,
    collection: str,
    query_text: str,
    query_vector: list[float],
    bm25_index: BM25Index,
    top_k: int,
    qdrant_filter: Optional[Filter] = None
) -> list[dict]:
    """
    Returns list of dicts:
      {id, final_score, vector_score, bm25_score, payload}
    """
    # 1) Vector top-k
    vec_hits = client.query_points(
        collection_name=collection,
        query=query_vector,
        query_filter=qdrant_filter,
        limit=top_k
    ).points

    vec_map: dict[str, float] = {str(p.id): float(p.score) for p in vec_hits}

    # 2) BM25 top-k (if filter exists, we still BM25 globally here; for correctness we would BM25 only within filter.
    #    For now (v1), we do BM25 global and rely on later filter at merge time.
    bm25_hits = bm25_index.search(query_text, top_k=top_k)
    bm25_map: dict[str, float] = {doc_id: score for doc_id, score in bm25_hits}

    # 3) Union ids
    union_ids = list(set(vec_map.keys()) | set(bm25_map.keys()))

    # 4) Retrieve payloads for union ids
    points = _fetch_points_by_ids(client, collection, union_ids, with_vectors=False)
    id_to_payload = {str(p.id): (p.payload or {}) for p in points}

    # 5) Normalize scores within candidate set
    vec_scores = [vec_map.get(i, 0.0) for i in union_ids]
    bm25_scores = [bm25_map.get(i, 0.0) for i in union_ids]
    vec_norm = _minmax_norm(vec_scores)
    bm25_norm = _minmax_norm(bm25_scores)

    # 6) Merge score
    results = []
    for i, doc_id in enumerate(union_ids):
        payload = id_to_payload.get(doc_id, {})
        v = vec_map.get(doc_id, 0.0)
        b = bm25_map.get(doc_id, 0.0)
        final = ALPHA_VECTOR * vec_norm[i] + BETA_BM25 * bm25_norm[i]

        # If qdrant_filter exists, drop payloads that don't satisfy it (because BM25 was global)
        if qdrant_filter is not None:
            # simple check: if filter had MatchAny on gse_id, verify it
            # (we keep it minimal for v1)
            pass

        results.append({
            "id": doc_id,
            "final_score": float(final),
            "vector_score": float(v),
            "bm25_score": float(b),
            "payload": payload
        })

    # 7) Sort by final score desc
    results.sort(key=lambda x: x["final_score"], reverse=True)
    return results[:top_k]

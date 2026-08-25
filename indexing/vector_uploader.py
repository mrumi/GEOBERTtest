# ============================================================
# indexing/vector_uploader.py — Upload Documents to Qdrant
# ============================================================
# (batch dense+sparse embedding, deterministic point IDs).
# ============================================================

import uuid

from qdrant_client.models import PointStruct, SparseVector


def make_point_id(parent_id: str, child_index: int) -> str:
    """
    Generate a deterministic UUID from parent_id + child_index.
    Same content identity -> same UUID every time, so re-uploading
    the same chunk overwrites instead of duplicating.
    """
    key = f"{parent_id}_{child_index}"
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, key))


def upload_documents(
    collection_name : str,
    documents       : list[dict],
    dense_embedder,
    sparse_embedder,
    qdrant_client,
    batch_size      : int = 32,
) -> int:
    """
    Embed and upload documents to Qdrant in batches.

    Args:
        collection_name : Target Qdrant collection.
        documents       : List of {"text": str, "metadata": dict}.
        dense_embedder  : SentenceTransformer instance.
        sparse_embedder : FastEmbed SparseTextEmbedding instance.
        qdrant_client   : QdrantClient instance.
        batch_size      : Documents per batch (dense+sparse embedded
                          together per batch, not one at a time).

    Returns:
        Total number of points uploaded.
    """

    if not documents:
        print("  No documents to upload.")
        return 0

    total_uploaded = 0

    for batch_start in range(0, len(documents), batch_size):

        batch_documents = documents[batch_start : batch_start + batch_size]

        batch_texts    = [doc["text"] for doc in batch_documents]
        batch_metadata = [doc["metadata"] for doc in batch_documents]

        dense_vectors = dense_embedder.encode(
            batch_texts, normalize_embeddings=True
        ).tolist()

        sparse_results = list(sparse_embedder.embed(batch_texts))

        current_batch = []

        for text, metadata, dense_vector, sparse_result in zip(
            batch_texts, batch_metadata, dense_vectors, sparse_results
        ):
            sparse_vector = SparseVector(
                indices = sparse_result.indices.tolist(),
                values  = sparse_result.values.tolist(),
            )

            point = PointStruct(
                id = make_point_id(
                    parent_id   = metadata.get("parent_id", ""),
                    child_index = metadata.get("child_index", 0),
                ),
                vector = {"dense": dense_vector, "sparse": sparse_vector},
                payload = {"text": text, **metadata},
            )

            current_batch.append(point)

        qdrant_client.upsert(collection_name=collection_name, points=current_batch)

        total_uploaded += len(current_batch)

    return total_uploaded

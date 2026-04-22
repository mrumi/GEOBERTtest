import uuid
from qdrant_client.models import PointStruct
from sentence_transformers import SentenceTransformer
from src.config import EMBED_MODEL

embedder = SentenceTransformer(EMBED_MODEL)


def upload_documents(client, collection_name, documents, batch_size=64):

    batch = []

    for doc in documents:

        embedding = embedder.encode(
            doc["text"],
            normalize_embeddings=True
        )

        point = PointStruct(
            id=str(uuid.uuid4()),
            vector=embedding.tolist(),
            payload={
                "text": doc["text"],
                **doc["metadata"]
            }
        )

        batch.append(point)

        if len(batch) >= batch_size:

            client.upsert(
                collection_name=collection_name,
                points=batch
            )

            batch = []

    if batch:

        client.upsert(
            collection_name=collection_name,
            points=batch
        )

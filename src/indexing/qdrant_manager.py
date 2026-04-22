from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams
from src.config import QDRANT_URL, STUDY_COLLECTION, SAMPLE_COLLECTION
from qdrant_client import QdrantClient
from src.config import QDRANT_URL, QDRANT_API_KEY
from qdrant_client.models import PayloadSchemaType


def get_qdrant_client():
    client = QdrantClient(
        url=QDRANT_URL,
        api_key=QDRANT_API_KEY
    )
    return client


def ensure_collection(client, collection_name, vector_size=768):

    existing = [c.name for c in client.get_collections().collections]

    if collection_name not in existing:
        print(f"Creating collection: {collection_name}")

        client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(
                size=vector_size,
                distance=Distance.COSINE
            )
        )

    else:
        print(f"Collection already exists: {collection_name}")


def initialize_collections(client):

    ensure_collection(client, STUDY_COLLECTION)
    ensure_collection(client, SAMPLE_COLLECTION)

    print("Collection initialization complete.")


def create_payload_indexes(client):

    study_fields = [
        "gse_id",
        "field",
        "organism",
        "assay_type",
        "tissue",
        "library_strategy",
        "library_source",
        "library_selection",
        "molecule",
        "instrument_model",
        "platform_id",
        "submission_date",
        "status"
    ]

    sample_fields = [
        "gse_id",
        "gsm_id",
        "organism",
        "assay_type",
        "title",
        "tissue",
        "disease",
        "genotype",
        "cell_line",
        "cell_type"
    ]

    for field in study_fields:
        client.create_payload_index(
            collection_name="geo_study_collection",
            field_name=field,
            field_schema=PayloadSchemaType.KEYWORD
        )

    for field in sample_fields:
        client.create_payload_index(
            collection_name="geo_sample_collection",
            field_name=field,
            field_schema=PayloadSchemaType.KEYWORD
        )

    print("Payload indexes created.")    

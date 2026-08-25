# ============================================================
# indexing/qdrant_manager.py — Collection Setup & Migration
# ============================================================

from qdrant_client import QdrantClient
from qdrant_client.models import (
    VectorParams,
    SparseVectorParams,
    SparseIndexParams,
    Distance,
    PayloadSchemaType,
    TextIndexParams,
    TokenizerType,
)


IDENTITY_FIELDS = [
    ("gse_id",           PayloadSchemaType.KEYWORD),
    ("gsm_id",           PayloadSchemaType.KEYWORD),
    ("parent_id",        PayloadSchemaType.KEYWORD),
    ("child_index",      PayloadSchemaType.INTEGER),
    ("level",            PayloadSchemaType.KEYWORD),
    ("field",            PayloadSchemaType.KEYWORD),
    ("is_superseries",   PayloadSchemaType.KEYWORD),
    ("is_subseries",     PayloadSchemaType.KEYWORD),
    ("parent_series_id", PayloadSchemaType.KEYWORD),
    ("subseries_ids",    PayloadSchemaType.KEYWORD),
    
]

CONTENT_FIELDS = [
    "organism", "strain", "tissue", "source_name", "specimen",
    "disease", "cell_line", "cell_type", "genotype",
    "assay_type", "library_strategy", "library_source",
    "library_selection", "molecule", "instrument_model",
    "platform_id", "title", "status",
]


def ensure_collection(
    client            : QdrantClient,
    collection_name   : str,
    dense_vector_size : int = 768,
) -> None:
    """
    Create a Qdrant collection with dense + sparse vectors and
    all payload indexes, if it doesn't already exist.
    """

    existing_collections = [c.name for c in client.get_collections().collections]

    if collection_name in existing_collections:
        print(f"Collection already exists  : {collection_name}")
        return

    print(f"Creating collection        : {collection_name}")

    client.create_collection(
        collection_name = collection_name,
        vectors_config  = {
            "dense": VectorParams(size=dense_vector_size, distance=Distance.COSINE)
        },
        sparse_vectors_config = {
            "sparse": SparseVectorParams(index=SparseIndexParams(on_disk=False))
        },
    )

    print(f"Collection created         : {collection_name}")

    for field_name, field_type in IDENTITY_FIELDS:
        client.create_payload_index(
            collection_name=collection_name, field_name=field_name, field_schema=field_type
        )
        print(f"  Keyword/int index created : {field_name}")

    for field_name in CONTENT_FIELDS:
        client.create_payload_index(
            collection_name = collection_name,
            field_name      = field_name,
            field_schema    = TextIndexParams(type="text", tokenizer=TokenizerType.WORD, lowercase=True),
        )
        print(f"  Text index created        : {field_name}")

    print(f"Collection setup complete  : {collection_name}\n")


def print_collection_info(client: QdrantClient, collection_name: str) -> None:
    info = client.get_collection(collection_name)
    print(f"Collection : {collection_name}")
    print(f"  Points   : {info.points_count}")
    print(f"  Status   : {info.status}")


# ============================================================
# Migration — Add Missing Payload Indexes
# ============================================================

def add_missing_payload_indexes(
    client          : QdrantClient,
    collection_name : str,
    keyword_fields  : list,
    text_fields     : list,
) -> None:
    """
    Add new payload indexes to an EXISTING collection without
    recreating it or touching existing data. Already-existing
    indexes are caught and silently skipped — safe to run
    multiple times (idempotent).
    """

    print(f"Checking indexes for: {collection_name}")

    for field_name, field_type in keyword_fields:
        try:
            client.create_payload_index(
                collection_name=collection_name, field_name=field_name, field_schema=field_type
            )
            print(f"  [added]  {field_name} (keyword/integer)")
        except Exception as error:
            print(f"  [skip]   {field_name} — {error}")

    for field_name in text_fields:
        try:
            client.create_payload_index(
                collection_name = collection_name,
                field_name      = field_name,
                field_schema    = TextIndexParams(type="text", tokenizer=TokenizerType.WORD, lowercase=True),
            )
            print(f"  [added]  {field_name} (text/lowercase)")
        except Exception as error:
            print(f"  [skip]   {field_name} — {error}")

    print(f"Migration complete: {collection_name}\n")


# Fields added in the schema update — kept here for reference/
# reuse if you need to run the migration against an older
# collection that predates this schema version.
NEW_KEYWORD_FIELDS_V2 = [
    ("is_superseries",   PayloadSchemaType.KEYWORD),
    ("is_subseries",     PayloadSchemaType.KEYWORD),
    ("parent_series_id", PayloadSchemaType.KEYWORD),
    ("subseries_ids",    PayloadSchemaType.KEYWORD),
]

NEW_TEXT_FIELDS_V2 = ["strain", "source_name"]

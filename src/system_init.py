import os
import json
from dotenv import load_dotenv

from qdrant_client import QdrantClient
from sentence_transformers import SentenceTransformer
from groq import Groq

from src.config import (
    QDRANT_URL,
    QDRANT_API_KEY,
    STUDY_COLLECTION,
    SAMPLE_COLLECTION,
    EMBED_MODEL,
    METADATA_DIR
)

from src.retrieval.bm25_index import BM25Index


# -------------------------
# Load environment
# -------------------------

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not GROQ_API_KEY:
    raise ValueError("GROQ_API_KEY not found in .env")


# -------------------------
# Qdrant Client
# -------------------------

print("Connecting to Qdrant...")

qdrant_client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)

print("Qdrant connected.")
print("Collections:", qdrant_client.get_collections())


# -------------------------
# Embedding Model
# -------------------------

print("Loading embedding model...")

embedder = SentenceTransformer(EMBED_MODEL)

print("Embedding model loaded:", EMBED_MODEL)


# -------------------------
# Groq Client
# -------------------------

groq_client = Groq(api_key=GROQ_API_KEY)

print("Groq client initialized.")


# -------------------------
# Load Metadata Index
# -------------------------

def load_metadata_index():

    auto_path = os.path.join(METADATA_DIR, "metadata_index.json")
    manual_path = os.path.join(METADATA_DIR, "manual_metadata.json")

    with open(auto_path) as f:
        auto_index = json.load(f)

    if os.path.exists(manual_path):
        with open(manual_path) as f:
            manual_index = json.load(f)

        for field, values in manual_index.items():

            auto_index.setdefault(field, [])

            merged = set(auto_index[field])
            merged.update(values)

            auto_index[field] = sorted(list(merged))

    return auto_index


print("Loading metadata index...")

metadata_index = load_metadata_index()

print("Metadata fields:", list(metadata_index.keys()))


# -------------------------
# Build BM25 Indexes
# -------------------------

print("\nBuilding BM25 indexes...")

bm25_study = BM25Index()
bm25_study.build_from_qdrant(
    client=qdrant_client,
    collection_name=STUDY_COLLECTION
)

print("Study BM25 docs:", len(bm25_study.doc_ids))


bm25_sample = BM25Index()
bm25_sample.build_from_qdrant(
    client=qdrant_client,
    collection_name=SAMPLE_COLLECTION
)

print("Sample BM25 docs:", len(bm25_sample.doc_ids))


print("\nSystem initialization complete.")

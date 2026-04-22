import os
from dotenv import load_dotenv


# ===============================
# Qdrant Configuration
# ===============================

load_dotenv()

QDRANT_URL = os.getenv("QDRANT_URL")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")



STUDY_COLLECTION = "geo_study_collection"
SAMPLE_COLLECTION = "geo_sample_collection"

# ===============================
# Embedding Model
# ===============================

EMBED_MODEL = "neuml/pubmedbert-base-embeddings"


# ===============================
# Project Directories
# ===============================

DATA_DIR = "data"

STUDY_DIR = "data/studies"
SAMPLE_DIR = "data/samples"

REGISTRY_DIR = "registry"
METADATA_DIR = "metadata"


# ===============================
# Indexing Parameters
# ===============================

VECTOR_SIZE = 768
CHUNK_SIZE = 500
UPLOAD_BATCH_SIZE = 64


# ===============================
TOP_K_STUDY = 7
TOP_K_SAMPLE = 5


# Standard cosine similarity gate (Qdrant cosine scores are typically 0..1, higher is better)
SIM_THRESHOLD = 0.35



# Hybrid weighting (tune later)
ALPHA_VECTOR = 0.65
BETA_BM25 = 0.35



# ===============================
# Metadata Schema Fields
# ===============================

DEFAULT_SCHEMA_FIELDS = [
    "organism",
    "tissue",
    "disease",
    "assay_type",
    "library_strategy",
    "library_source",
    "library_selection",
    "molecule",
    "instrument_model",
    "status",
    "genotype",
    "cell_line",
    "cell_type",
]


# ===============================
# Invalid Metadata Values
# ===============================

INVALID_VALUES = {
    "na",
    "n a",
    "other",
    "unknown",
    "tissue",
    ""
}
from types import SimpleNamespace

settings = SimpleNamespace(
    QDRANT_URL=QDRANT_URL,
    QDRANT_API_KEY=QDRANT_API_KEY,
    MAX_EVIDENCE=5,
    DEBUG_RETRIEVAL=False,
    ENABLE_STREAMING=True
)

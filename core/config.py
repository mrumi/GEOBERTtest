# ============================================================
# core/config.py — Centralized Configuration
# ============================================================
# Configuration Constants with a pydantic
# Settings class instead of raw module-level variables.
# - pydantic-settings reads from environment variables /
#  .env automatically, validates types, and gives one
#  single object to import everywhere instead of scattered globals.     
#  Every constant, tunable value, and directory path
#  is preserved here with the SAME name and SAME default value
# ============================================================

import os
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):

    model_config = SettingsConfigDict(
        env_file           = ".env",
        env_file_encoding  = "utf-8",
        extra              = "ignore",
    )

    # ============================================================
    # Secrets / Connection Strings (from Cell 1 env vars)
    # ============================================================
    GROQ_API_KEY : str
    QDRANT_URL   : str = "http://localhost:6333"

    # Optional — only needed for a secured/cloud Qdrant instance.
    # Local self-hosted Qdrant (Docker, no auth enabled) needs no
    # API key at all; leave unset in .env for local dev.
    QDRANT_API_KEY : str | None = None

    # Optional — our models (PubMedBERT, SPLADE, MiniLM cross-encoder)
    # are all public, so this isn't required for downloads to work.
    # Set it anyway to get higher HuggingFace Hub rate limits and
    # faster downloads (removes the "unauthenticated requests"
    # warning you saw at startup). Get a token from:
    # https://huggingface.co/settings/tokens
    HF_TOKEN : str | None = None

    # PostgreSQL for sessions/users,
    # added for the multi-user API.
    DATABASE_URL : str

    # JWT auth secret.
    JWT_SECRET_KEY         : str 
    JWT_ALGORITHM          : str 
    JWT_EXPIRE_MINUTES     : int 

    # ============================================================
    # Collection Names 
    # ============================================================
    STUDY_COLLECTION  : str = "geo_study_collection"
    SAMPLE_COLLECTION : str = "geo_sample_collection"

    # ============================================================
    # Model Names 
    # ============================================================
    DENSE_EMBED_MODEL    : str = "neuml/pubmedbert-base-embeddings"
    SPARSE_EMBED_MODEL   : str = "prithivida/Splade_PP_en_v1"
    CROSS_ENCODER_MODEL  : str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    TOKENIZER_MODEL      : str = "neuml/pubmedbert-base-embeddings"

    # LLM models 
    # llama-3.1-8b-instant llama-3.3-70b-versatile  meta-llama/llama-4-scout-17b-16e-instruct
    # openai/gpt-oss-120b qwen/qwen3-32b
    
    GROQ_QUERY_MODEL  : str = "openai/gpt-oss-120b"
    GROQ_ANSWER_MODEL : str = "openai/gpt-oss-120b"

    # ============================================================
    # Directory Paths 
    # ============================================================
    STUDY_DIR    : str = "data/studies"
    SAMPLE_DIR   : str = "data/samples"
    REGISTRY_DIR : str = "registry"
    CACHE_DIR    : str = "cache"

    # ============================================================
    # Registry File Paths 
    # ============================================================
    @property
    def STUDY_REGISTRY_PATH(self) -> str:
        return os.path.join(self.REGISTRY_DIR, "indexed_studies.json")

    @property
    def SAMPLE_REGISTRY_PATH(self) -> str:
        return os.path.join(self.REGISTRY_DIR, "indexed_samples.json")

    @property
    def ONTOLOGY_CACHE_DB(self) -> str:
        return os.path.join(self.CACHE_DIR, "ontology_cache.db")

    # ============================================================
    # Chunking Parameters 
    # ============================================================
    CHUNK_SIZE_TOKENS    : int = 256
    CHUNK_OVERLAP_TOKENS : int = 50
    NEIGHBOR_WINDOW       : int = 1

    # ============================================================
    # Retrieval Parameters 
    # ============================================================
    TOP_K_STUDY_RETRIEVAL     : int = 250
    TOP_K_SAMPLE_RETRIEVAL    : int = 50
    TOP_K_AFTER_RERANK        : int = 30
    TOP_K_SAMPLE_AFTER_RERANK : int = 10
    SIM_THRESHOLD              : float = 0.20

    # ============================================================
    # Hybrid Search Weights 
    # ============================================================
    ALPHA_DENSE  : float = 0.65
    ALPHA_SPARSE : float = 0.35

    # ============================================================
    # Metadata Boost Values 
    # ============================================================
    EXACT_PAYLOAD_MATCH_BOOST : float = 0.15
    FIELD_FOCUS_BOOST         : float = 0.15
    FIELD_MATCH_BOOST         : float = 0.10

    def ensure_directories(self) -> None:
        """
        Create local working directories if they don't exist.
        Mirrors Cell 2's os.makedirs() calls. Call this once at
        app startup (see core/clients.py lifespan hook) — NOT
        at import time, so importing this module has no side
        effects (important for testing and for tools like
        Alembic that import config without wanting to touch disk).
        """
        os.makedirs(self.REGISTRY_DIR, exist_ok=True)
        os.makedirs(self.CACHE_DIR,    exist_ok=True)


# Single shared settings instance — import this everywhere:
#   from core.config import settings
settings = Settings()
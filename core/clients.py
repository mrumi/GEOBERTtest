# ============================================================
# core/clients.py — Model & Client Initialization
# ============================================================
# Imports, Connections, Model Init
#   wrap all initialization in a single function,
#   AppClients.load(), called EXACTLY ONCE at app startup via
#   FastAPI's lifespan event (see main.py). The resulting object
#   is stored on app.state and handed to route handlers via
#   dependency injection (see api/dependencies.py) — never
#   re-created per request.
# ============================================================

from dataclasses import dataclass
import os

from qdrant_client import QdrantClient
from sentence_transformers import SentenceTransformer, CrossEncoder
from fastembed import SparseTextEmbedding
from groq import Groq
from transformers import AutoTokenizer

from core.config import Settings


@dataclass
class AppClients:
    """
    Container for every heavyweight client/model the app needs.
    Created once at startup, reused for the lifetime of the process.
    """
    qdrant_client   : QdrantClient
    groq_client     : Groq
    dense_embedder  : SentenceTransformer
    sparse_embedder : SparseTextEmbedding
    cross_encoder   : CrossEncoder
    tokenizer       : AutoTokenizer   # used by indexing/chunker.py

    @classmethod
    def load(cls, settings: Settings) -> "AppClients":
        """
        Initialize every client and model exactly once.

        Args:
            settings: The app's Settings instance (core/config.py).

        Returns:
            A fully populated AppClients instance.

        Raises:
            ValueError: if GROQ_API_KEY is missing (mirrors the
                        explicit check).
        """

        if not settings.GROQ_API_KEY:
            raise ValueError("GROQ_API_KEY not set — check your .env file")

        # huggingface_hub (used internally by sentence-transformers,
        # fastembed, and transformers) reads the HF_TOKEN env var
        # directly from os.environ — pydantic-settings does NOT
        # auto-export declared fields into the process environment,
         
        
        if settings.HF_TOKEN:
            os.environ["HF_TOKEN"] = settings.HF_TOKEN

        print("Initializing Groq client...")
        groq_client = Groq(api_key=settings.GROQ_API_KEY)

        print(f"Connecting to Qdrant at {settings.QDRANT_URL}...")
        qdrant_client = QdrantClient(
            url     = settings.QDRANT_URL,
            api_key = settings.QDRANT_API_KEY,   # None is fine — local Qdrant needs no key
        )
        collections = qdrant_client.get_collections()
        print(f"Connected. Existing collections: {[c.name for c in collections.collections]}")

        print(f"Loading dense embedder: {settings.DENSE_EMBED_MODEL} ...")
        dense_embedder = SentenceTransformer(settings.DENSE_EMBED_MODEL)

        print(f"Loading sparse embedder: {settings.SPARSE_EMBED_MODEL} ...")
        sparse_embedder = SparseTextEmbedding(model_name=settings.SPARSE_EMBED_MODEL)

        print(f"Loading cross-encoder: {settings.CROSS_ENCODER_MODEL} ...")
        cross_encoder = CrossEncoder(settings.CROSS_ENCODER_MODEL, max_length=512)

        print(f"Loading tokenizer: {settings.TOKENIZER_MODEL} ...")
        tokenizer = AutoTokenizer.from_pretrained(settings.TOKENIZER_MODEL)

        print("All clients and models initialized.")

        return cls(
            qdrant_client   = qdrant_client,
            groq_client     = groq_client,
            dense_embedder  = dense_embedder,
            sparse_embedder = sparse_embedder,
            cross_encoder   = cross_encoder,
            tokenizer       = tokenizer,
        )
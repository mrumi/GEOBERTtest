# src/retrieval/bm25_index.py

import re
from typing import Optional, List, Tuple
from qdrant_client import QdrantClient
from rank_bm25 import BM25Okapi


# -----------------------------
# Tokenizer
# -----------------------------

_TOKEN_RE = re.compile(r"[A-Za-z0-9_+\-]+")


def simple_tokenize(text: str) -> List[str]:
    """
    Lightweight tokenizer for BM25.
    """
    if not text:
        return []

    return [t.lower() for t in _TOKEN_RE.findall(text)]


# -----------------------------
# BM25 Index
# -----------------------------

class BM25Index:
    """
    In-memory BM25 index built from Qdrant payload["text"].

    WARNING:
    This loads documents into RAM.

    Recommended usage:
        • STUDY collection only
        • < 300k documents
    """

    def __init__(self):

        self.bm25: Optional[BM25Okapi] = None
        self.doc_ids: List[str] = []
        self.doc_meta: List[dict] = []
        self.corpus_tokens: List[List[str]] = []

    # --------------------------------
    # Build index from Qdrant
    # --------------------------------

    def build_from_qdrant(
        self,
        client: QdrantClient,
        collection_name: str,
        scroll_limit: int = 2000,
        max_docs: int = 300_000
    ) -> None:

        self.doc_ids = []
        self.doc_meta = []
        self.corpus_tokens = []

        offset = None
        count = 0

        while True:

            points, offset = client.scroll(
                collection_name=collection_name,
                limit=scroll_limit,
                offset=offset,
                with_payload=True,
                with_vectors=False
            )

            if not points:
                break

            for p in points:

                payload = p.payload or {}

                text = payload.get("text", "")
                tokens = simple_tokenize(text)

                if not tokens:
                    continue

                self.doc_ids.append(str(p.id))

                self.doc_meta.append({
                    "gse_id": payload.get("gse_id"),
                    "gsm_id": payload.get("gsm_id"),
                    "field": payload.get("field"),
                    "level": payload.get("level"),
                })

                self.corpus_tokens.append(tokens)

                count += 1

                if count >= max_docs:
                    print(f"BM25 limit reached ({max_docs})")
                    break

            if offset is None or count >= max_docs:
                break

        if self.corpus_tokens:
            self.bm25 = BM25Okapi(self.corpus_tokens)
        else:
            self.bm25 = None

        print(f"BM25 built for {len(self.doc_ids)} documents")

    # --------------------------------
    # Search
    # --------------------------------

    def search(
        self,
        query: str,
        top_k: int = 10
    ) -> List[Tuple[str, float]]:

        if not self.bm25:
            return []

        q_tokens = simple_tokenize(query)

        if not q_tokens:
            return []

        scores = self.bm25.get_scores(q_tokens)

        ranked = sorted(
            range(len(scores)),
            key=lambda i: scores[i],
            reverse=True
        )[:top_k]

        return [
            (self.doc_ids[i], float(scores[i]))
            for i in ranked
        ]

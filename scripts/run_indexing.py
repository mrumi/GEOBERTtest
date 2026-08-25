# ============================================================
# scripts/run_indexing.py — Full Indexing Pipeline (CLI)
# ============================================================
#
# This is a STANDALONE OFFLINE SCRIPT, not part of the FastAPI
# app — run it manually whenever new study/
# sample JSON files need indexing:
#
#     python scripts/run_indexing.py
#
# It intentionally loads its own AppClients instance rather than
# sharing the API's — indexing and serving are different
# processes with different lifecycles (see indexing/ vs rag/
# module docstrings for the full reasoning).
# ============================================================

import os
import sys
import json
from tqdm import tqdm

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.config import settings
from core.clients import AppClients

from indexing.chunker import split_text_into_token_chunks
from indexing.document_parser import parse_study_json, parse_sample_json
from indexing.vector_uploader import upload_documents
from indexing.qdrant_manager import ensure_collection
from indexing.registry_manager import (
    load_registry,
    save_registry,
    print_registry_status,
)


def main():

    settings.ensure_directories()

    print("Loading models and connecting to Qdrant...")
    clients = AppClients.load(settings)

    # ============================================================
    # Ensure Qdrant Collections Exist
    # ============================================================
    #
    # The indexing pipeline uses two collections:
    #   1. Study collection
    #   2. Sample collection
    #
    # Create them if they don't already exist.
    # If they already exist, ensure_collection() does nothing.
    # ============================================================

    print("=" * 55)
    print("Checking Qdrant Collections")
    print("=" * 55)

    ensure_collection(
        client=clients.qdrant_client,
        collection_name=settings.STUDY_COLLECTION,
        dense_vector_size=768,
    )

    ensure_collection(
        client=clients.qdrant_client,
        collection_name=settings.SAMPLE_COLLECTION,
        dense_vector_size=768,
    )

    # ============================================================
    # Token Chunking Function
    # ============================================================

    def split_text_fn(text: str, parent_id: str) -> list[dict]:
        return split_text_into_token_chunks(
            text=text,
            parent_id=parent_id,
            tokenizer=clients.tokenizer,
            chunk_size=settings.CHUNK_SIZE_TOKENS,
            overlap_size=settings.CHUNK_OVERLAP_TOKENS,
        )

    # ============================================================
    # Load Indexing Registries
    # ============================================================

    indexed_studies = load_registry(settings.STUDY_REGISTRY_PATH)
    indexed_samples = load_registry(settings.SAMPLE_REGISTRY_PATH)

    print_registry_status(indexed_studies, indexed_samples)

    # ============================================================
    # Phase 1 — Index Studies
    # ============================================================

    print("=" * 55)
    print("Phase 1 — Indexing Studies")
    print("=" * 55)

    study_files = [
        f for f in os.listdir(settings.STUDY_DIR)
        if f.endswith(".json")
    ]

    print(f"Study files found: {len(study_files)}\n")

    total_study_chunks_uploaded = 0
    studies_skipped = 0
    studies_indexed = 0

    for study_file in tqdm(study_files, desc="Indexing studies"):

        study_file_path = os.path.join(
            settings.STUDY_DIR,
            study_file
        )

        with open(study_file_path, "r", encoding="utf-8") as f:
            study_gse_id = json.load(f).get("gse_id", "")

        if study_gse_id in indexed_studies:
            tqdm.write(
                f"  [skip]   {study_gse_id} already indexed"
            )
            studies_skipped += 1
            continue

        tqdm.write(
            f"  [index]  {study_gse_id}"
        )

        study_documents = parse_study_json(
            study_file_path,
            split_text_fn=split_text_fn
        )

        tqdm.write(
            f"           {len(study_documents)} chunks produced"
        )

        uploaded = upload_documents(
            collection_name=settings.STUDY_COLLECTION,
            documents=study_documents,
            dense_embedder=clients.dense_embedder,
            sparse_embedder=clients.sparse_embedder,
            qdrant_client=clients.qdrant_client,
            batch_size=32,
        )

        tqdm.write(
            f"           {uploaded} chunks uploaded"
        )

        indexed_studies.add(study_gse_id)

        save_registry(
            settings.STUDY_REGISTRY_PATH,
            indexed_studies
        )

        total_study_chunks_uploaded += uploaded
        studies_indexed += 1

    print("\nStudy indexing complete.")
    print(f"  Studies indexed  : {studies_indexed}")
    print(f"  Studies skipped  : {studies_skipped}")
    print(f"  Total chunks     : {total_study_chunks_uploaded}\n")

    # ============================================================
    # Phase 2 — Index Samples
    # ============================================================

    print("=" * 55)
    print("Phase 2 — Indexing Samples")
    print("=" * 55)

    sample_files = [
        f for f in os.listdir(settings.SAMPLE_DIR)
        if f.endswith(".json")
    ]

    print(f"Sample files found: {len(sample_files)}\n")

    total_sample_docs_uploaded = 0
    samples_skipped = 0
    samples_indexed = 0

    for sample_file in tqdm(sample_files, desc="Indexing samples"):

        sample_file_path = os.path.join(
            settings.SAMPLE_DIR,
            sample_file
        )

        tqdm.write(
            f"  [file]   {sample_file}"
        )

        # Samples already contain their own metadata.
        sample_documents = parse_sample_json(
            file_path=sample_file_path
        )

        new_sample_documents = []

        for sample_doc in sample_documents:

            gsm_id = sample_doc["metadata"].get(
                "gsm_id",
                ""
            )

            if gsm_id in indexed_samples:
                samples_skipped += 1
                continue

            new_sample_documents.append(sample_doc)

        if not new_sample_documents:
            tqdm.write(
                "           all samples already indexed — skipping"
            )
            continue

        tqdm.write(
            f"           {len(new_sample_documents)} "
            f"new samples to upload"
        )

        uploaded = upload_documents(
            collection_name=settings.SAMPLE_COLLECTION,
            documents=new_sample_documents,
            dense_embedder=clients.dense_embedder,
            sparse_embedder=clients.sparse_embedder,
            qdrant_client=clients.qdrant_client,
            batch_size=32,
        )

        tqdm.write(
            f"           {uploaded} samples uploaded"
        )

        for sample_doc in new_sample_documents:

            gsm_id = sample_doc["metadata"].get(
                "gsm_id",
                ""
            )

            indexed_samples.add(gsm_id)

        save_registry(
            settings.SAMPLE_REGISTRY_PATH,
            indexed_samples
        )

        total_sample_docs_uploaded += uploaded
        samples_indexed += uploaded

    print("\nSample indexing complete.")
    print(f"  Samples indexed  : {samples_indexed}")
    print(f"  Samples skipped  : {samples_skipped}")
    print(f"  Total uploaded   : {total_sample_docs_uploaded}\n")

    # ============================================================
    # Final Registry Status
    # ============================================================

    print("=" * 55)
    print("Final Registry Status")
    print("=" * 55)

    print_registry_status(
        indexed_studies,
        indexed_samples
    )


if __name__ == "__main__":
    main()
import os
import json
from tqdm import tqdm

from src.config import STUDY_DIR, SAMPLE_DIR
from src.indexing.qdrant_manager import (
    create_payload_indexes,
    get_qdrant_client,
    initialize_collections,
)
from src.indexing.document_parser import parse_study_json, parse_sample_json
from src.indexing.vector_uploader import upload_documents
from src.indexing.registry_manager import (
    load_registry,
    save_registry,
    STUDY_REGISTRY,
    SAMPLE_REGISTRY,
)
from src.indexing.metadata_index import build_and_save_metadata_index


def build_study_metadata_map() -> dict:
    study_metadata_map = {}

    if not os.path.exists(STUDY_DIR):
        raise FileNotFoundError(f"Study directory not found: {STUDY_DIR}")

    for file in os.listdir(STUDY_DIR):
        if not file.endswith(".json"):
            continue

        file_path = os.path.join(STUDY_DIR, file)

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            gse_id = data.get("gse_id")
            if not gse_id:
                print(f"Skipping study file without gse_id: {file}")
                continue

            exp = data.get("experimental_design", {}) or {}

            study_metadata_map[gse_id] = {
                "organism": data.get("organism"),
                "assay_type": exp.get("experimental_type"),
                "study_tissue": exp.get("tissue"),
            }

        except Exception as e:
            print(f"Failed to read study metadata from {file}: {e}")

    return study_metadata_map


def index_studies(client, indexed_studies: set) -> set:
    if not os.path.exists(STUDY_DIR):
        raise FileNotFoundError(f"Study directory not found: {STUDY_DIR}")

    files = [f for f in os.listdir(STUDY_DIR) if f.endswith(".json")]

    for file in tqdm(files, desc="Indexing studies"):
        file_path = os.path.join(STUDY_DIR, file)

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            gse_id = data.get("gse_id")
            if not gse_id:
                print(f"Skipping study file without gse_id: {file}")
                continue

            if gse_id in indexed_studies:
                continue

            docs = parse_study_json(file_path)

            if not docs:
                print(f"No study documents parsed for {gse_id}")
                indexed_studies.add(gse_id)
                continue

            upload_documents(client, "geo_study_collection", docs)
            indexed_studies.add(gse_id)

        except Exception as e:
            print(f"Failed to index study file {file}: {e}")

    return indexed_studies


def index_samples(client, indexed_samples: set, study_metadata_map: dict) -> set:
    if not os.path.exists(SAMPLE_DIR):
        raise FileNotFoundError(f"Sample directory not found: {SAMPLE_DIR}")

    files = [f for f in os.listdir(SAMPLE_DIR) if f.endswith(".json")]

    for file in tqdm(files, desc="Indexing samples"):
        file_path = os.path.join(SAMPLE_DIR, file)

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            gse_id = data.get("gse_id")
            if not gse_id:
                print(f"Skipping sample file without gse_id: {file}")
                continue

            if gse_id in indexed_samples:
                continue

            docs = parse_sample_json(file_path, study_metadata_map)

            if not docs:
                print(f"No sample documents parsed for {gse_id}")
                indexed_samples.add(gse_id)
                continue

            upload_documents(client, "geo_sample_collection", docs)
            indexed_samples.add(gse_id)

        except Exception as e:
            print(f"Failed to index sample file {file}: {e}")

    return indexed_samples


def run_indexing():
    print("Connecting to Qdrant...")
    client = get_qdrant_client()

    print("Initializing collections...")
    initialize_collections(client)

    print("Creating payload indexes...")
    create_payload_indexes(client)

    indexed_studies = load_registry(STUDY_REGISTRY)
    indexed_samples = load_registry(SAMPLE_REGISTRY)

    print(f"Loaded {len(indexed_studies)} indexed studies from registry")
    print(f"Loaded {len(indexed_samples)} indexed samples from registry")

    print("Building study metadata map...")
    study_metadata_map = build_study_metadata_map()

    print("Starting study indexing...")
    indexed_studies = index_studies(client, indexed_studies)
    save_registry(STUDY_REGISTRY, indexed_studies)
    print(f"Study indexing complete. Total indexed studies: {len(indexed_studies)}")

    print("Starting sample indexing...")
    indexed_samples = index_samples(client, indexed_samples, study_metadata_map)
    save_registry(SAMPLE_REGISTRY, indexed_samples)
    print(f"Sample indexing complete. Total indexed samples: {len(indexed_samples)}")

    print("Building metadata index...")
    metadata_index = build_and_save_metadata_index(client)
    print("Metadata index built.")
    print("Metadata fields:", list(metadata_index.keys()))

    print("All indexing steps complete.")


if __name__ == "__main__":
    run_indexing()

import os
import json
import re

from src.config import (
    METADATA_DIR,
    DEFAULT_SCHEMA_FIELDS,
    INVALID_VALUES,
    STUDY_COLLECTION,
    SAMPLE_COLLECTION
)


# -------------------------
# Normalization
# -------------------------

def _norm(s: str) -> str:
    s = (s or "").strip().lower()

    s = s.replace("_", " ").replace("-", " ")

    s = re.sub(r"[^\w\s\+]", " ", s)

    s = re.sub(r"\s+", " ", s)

    return s.strip()


# -------------------------
# Payload extractor
# -------------------------

def _get_payload_value(payload: dict, field: str):

    if payload is None:
        return None

    if field in payload and payload[field] not in (None, "", []):
        return payload[field]

    meta = payload.get("metadata")

    if isinstance(meta, dict):
        return meta.get(field)

    return None


# -------------------------
# Multi-value splitting
# -------------------------

def _split_values(v):

    if v is None:
        return []

    if isinstance(v, list):
        return v

    parts = re.split(r"[;,|]", str(v))

    return [p.strip() for p in parts if p.strip()]


# -------------------------
# Metadata index builder
# -------------------------

def build_metadata_value_index(
    qdrant_client,
    collections,
    schema_fields=DEFAULT_SCHEMA_FIELDS,
    scroll_limit=256,
    max_points=200000
):

    index = {f: set() for f in schema_fields}

    seen = 0

    for col in collections:

        offset = None

        while True:

            points, offset = qdrant_client.scroll(
                collection_name=col,
                limit=scroll_limit,
                offset=offset,
                with_payload=True,
                with_vectors=False,
            )

            for pt in points:

                payload = pt.payload or {}

                for field in schema_fields:

                    v = _get_payload_value(payload, field)

                    if v is None:
                        continue

                    values = _split_values(v)

                    for item in values:

                        nv = _norm(str(item))

                        if not nv:
                            continue

                        if nv in INVALID_VALUES:
                            continue

                        if field == "status" and "public" in nv:
                            nv = "public"

                        index[field].add(nv)

                seen += 1

                if seen >= max_points:
                    break

            if offset is None or seen >= max_points:
                break

    return index


# -------------------------
# Save metadata index
# -------------------------

def save_metadata_index(metadata_index):

    os.makedirs(METADATA_DIR, exist_ok=True)

    path = os.path.join(METADATA_DIR, "metadata_index.json")

    with open(path, "w") as f:
        json.dump({k: list(v) for k, v in metadata_index.items()}, f, indent=2)


# -------------------------
# Load metadata index
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


# -------------------------
# Full metadata indexing pipeline
# -------------------------

def build_and_save_metadata_index(qdrant_client):

    metadata_index = build_metadata_value_index(
        qdrant_client,
        collections=[STUDY_COLLECTION, SAMPLE_COLLECTION]
    )

    save_metadata_index(metadata_index)

    return metadata_index

# ============================================================
# indexing/registry_manager.py — Track Indexed Documents
# ============================================================


import os
import json


def load_registry(registry_file_path: str) -> set:
    """Load the registry of already-indexed document IDs as a set."""
    if not os.path.exists(registry_file_path):
        return set()

    with open(registry_file_path, "r", encoding="utf-8") as file:
        id_list = json.load(file)

    return set(id_list)


def save_registry(registry_file_path: str, indexed_ids: set) -> None:
    """Save the current set of indexed IDs to the registry file."""
    with open(registry_file_path, "w", encoding="utf-8") as file:
        json.dump(sorted(list(indexed_ids)), file, indent=2)


def print_registry_status(indexed_studies: set, indexed_samples: set) -> None:
    """Print a summary of the current registry state."""
    print("=== Registry Status ===")
    print(f"Indexed studies : {len(indexed_studies)}")
    print(f"Indexed samples : {len(indexed_samples)}")

    if indexed_studies:
        print(f"\nIndexed GSE IDs:")
        for gse_id in sorted(indexed_studies):
            print(f"  {gse_id}")

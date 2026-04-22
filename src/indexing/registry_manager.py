import os
import json
from src.config import REGISTRY_DIR

STUDY_REGISTRY = os.path.join(REGISTRY_DIR, "indexed_studies.json")
SAMPLE_REGISTRY = os.path.join(REGISTRY_DIR, "indexed_samples.json")


def load_registry(path):

    if os.path.exists(path):

        with open(path) as f:
            return set(json.load(f))

    return set()


def save_registry(path, data):

    with open(path, "w") as f:

        json.dump(sorted(list(data)), f, indent=2)

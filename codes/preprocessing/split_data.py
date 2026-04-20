import json
import os
from pathlib import Path
from typing import Dict, Any, List


# ==========================
# CONFIG
# ==========================
INPUT_JSON_PATH = "gse_data.json"   # your original file
OUTPUT_BASE_DIR = "processed_data"


# ==========================
# UTILS
# ==========================
def ensure_dirs(base: str):
    for sub in ["raw", "studies", "samples", "runs"]:
        Path(base, sub).mkdir(parents=True, exist_ok=True)


def write_json(path: Path, data: Any):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


# ==========================
# SPLIT LOGIC
# ==========================
def split_gse_record(gse: Dict[str, Any], output_dir: str):
    """
    Splits ONE GSE record into study / samples / runs
    WITHOUT removing any information.
    """

    gse_id = gse.get("gse_id", "UNKNOWN_GSE")

    # ---------- RAW ----------
    write_json(
        Path(output_dir, "raw", f"{gse_id}.raw.json"),
        gse
    )

    # ---------- STUDY ----------
    study_doc = {
        "doc_type": "study",
        "study_id": gse_id,
        "core": {
            "gse_id": gse.get("gse_id"),
            "title": gse.get("title"),
            "organism": gse.get("organism"),
            "summary": gse.get("summary"),
            "platform_id": gse.get("platform_id"),
            "supplementary_files": gse.get("supplementary_files")
        },
        "metadata": {
            "metadata_json": gse.get("metadata_json"),
            "sample_common_metadata": gse.get("sample_ids", {}).get("common_metadata"),
            "prjna_common_metadata": gse.get("PRJNA_RUN_METADATA", {}).get("common_metadata")
        }
    }

    write_json(
        Path(output_dir, "studies", f"{gse_id}.study.json"),
        study_doc
    )

    # ---------- SAMPLES ----------
    samples: List[Dict[str, Any]] = []

    sample_list = gse.get("sample_ids", {}).get("samples_specific_metadata", [])

    for sample in sample_list:
        sample_doc = {
            "doc_type": "sample",
            "study_id": gse_id,
            "gsm_id": sample.get("gsm_id"),
            "title": sample.get("title"),
            "extra_metadata": sample.get("extra_metadata"),
            "inherited_common_metadata": gse.get("sample_ids", {}).get("common_metadata")
        }
        samples.append(sample_doc)

    write_json(
        Path(output_dir, "samples", f"{gse_id}.samples.json"),
        samples
    )

    # ---------- RUNS ----------
    runs: List[Dict[str, Any]] = []

    run_list = gse.get("PRJNA_RUN_METADATA", {}).get("runs_specific_metadata", [])

    for run in run_list:
        run_doc = {
            "doc_type": "run",
            "study_id": gse_id,
            "run_id": run.get("Run"),
            "sample_name": run.get("SampleName"),
            "gsm_id": run.get("LibraryName"),
            "experiment": run.get("Experiment"),
            "all_metadata": run
        }
        runs.append(run_doc)

    write_json(
        Path(output_dir, "runs", f"{gse_id}.runs.json"),
        runs
    )


# ==========================
# MAIN
# ==========================
def main():
    ensure_dirs(OUTPUT_BASE_DIR)

    with open(INPUT_JSON_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Supports:
    # - list of GSEs
    # - single GSE object
    if isinstance(data, dict):
        data = [data]

    for gse in data:
        split_gse_record(gse, OUTPUT_BASE_DIR)

    print(f"✅ Finished processing {len(data)} GSE record(s)")


if __name__ == "__main__":
    main()

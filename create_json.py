import json
from pathlib import Path
import re
from typing import Dict, Any, List


BIO_FIELDS = {
    "tissue", "cell line", "cell type", "genotype",
    "specimen", "disease", "organism", "strain"
}

COND_FIELDS = {
    "treatment", "time", "timepoint", "age", "stage", "exposure"
}


def normalize(k):
    return k.strip().lower().replace(" ", "_")


def parse_characteristics(chars):
    bio = {}
    cond = {}
    other = {}

    for c in chars or []:
        if ":" not in c:
            continue

        k, v = c.split(":", 1)
        k_l = k.lower().strip()
        v = v.strip()

        if k_l in BIO_FIELDS:
            bio[normalize(k_l)] = v
        elif k_l in COND_FIELDS:
            cond[normalize(k_l)] = v
        else:
            other[normalize(k_l)] = v

    return bio, cond, other


def parse_relations(relations):
    biosample = None
    sra = None

    for r in relations or []:
        if "SAMN" in r:
            biosample = r.split(":")[-1].strip()
        if "SRX" in r:
            sra = r.split(":")[-1].strip()

    return biosample, sra


def generate_samples_semantic(raw):
    gse_id = raw["gse_id"]
    raw_samples = raw["sample_ids"]["samples_specific_metadata"]

    samples = []

    for s in raw_samples:
        meta = s.get("extra_metadata", {})

        bio, cond, other_chars = parse_characteristics(
            meta.get("characteristics_ch1")
        )

        biosample, sra = parse_relations(meta.get("relation"))

        sample = {
            "gsm_id": s.get("gsm_id"),
            "title": s.get("title"),

            "biological_metadata": {
                "tissue": bio.get("tissue"),
                "cell_line": bio.get("cell_line"),
                "cell_type": bio.get("cell_type"),
                "genotype": bio.get("genotype"),
                "specimen": bio.get("specimen"),
                "disease": bio.get("disease"),
                "organism": bio.get("organism"),
                "strain": bio.get("strain")
            },

            "experimental_conditions": {
                "treatment": cond.get("treatment"),
                "time": cond.get("time"),
                "age": cond.get("age"),
                "exposure": cond.get("exposure")
            },

            "technical_metadata": {
                "library_strategy": (
                    s.get("library_strategy") or
                    next(iter(meta.get("library_strategy", [])), None)
                ),
                "library_source": next(iter(meta.get("library_source", [])), None),
                "library_selection": next(iter(meta.get("library_selection", [])), None),
                "instrument_model": next(iter(meta.get("instrument_model", [])), None),
                "data_processing": meta.get("data_processing")
            },

            "descriptions": meta.get("description"),

            "accessions": {
                "biosample": biosample,
                "sra_experiment": sra
            },

            # 🔒 NOTHING LOST
            "raw_extra_metadata": other_chars
        }

        samples.append(sample)

    return {
        "gse_id": gse_id,
        "sample_summary": {
            "total_samples": len(samples)
        },
        "samples": samples
    }


def remove_nulls(obj):
    """
    Recursively remove None, empty lists, and empty dicts
    from nested dictionaries and lists.
    """
    if isinstance(obj, dict):
        cleaned = {}
        for k, v in obj.items():
            v_clean = remove_nulls(v)
            if v_clean is not None and v_clean != {} and v_clean != []:
                cleaned[k] = v_clean
        return cleaned

    elif isinstance(obj, list):
        cleaned_list = []
        for item in obj:
            item_clean = remove_nulls(item)
            if item_clean is not None and item_clean != {} and item_clean != []:
                cleaned_list.append(item_clean)
        return cleaned_list

    else:
        return obj



def save_samples_json(raw_json_path, output_dir):
    raw = json.loads(Path(raw_json_path).read_text(encoding="utf-8"))

    out = generate_samples_semantic(raw)

    # 🔥 REMOVE NULL / EMPTY FIELDS
    out = remove_nulls(out)

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    out_path = out_dir / f"{out['gse_id']}.samples.json"
    out_path.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"✅ Samples semantic JSON saved → {out_path}")


def _first(val):
    """Return first element if list, else value."""
    if isinstance(val, list) and val:
        return val[0]
    return val


def _join(val, sep="; "):
    """Join list values into string."""
    if isinstance(val, list):
        return sep.join(str(v) for v in val if v)
    return val


def generate_study_semantic(raw: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert raw GEO JSON into clean study-level semantic JSON.
    """

    gse_id = raw.get("gse_id")
    title = raw.get("title")
    organism = raw.get("organism")
    summary = raw.get("summary")

    metadata = raw.get("metadata_json", {})
    samples = raw.get("sample_ids", {})
    common_meta = samples.get("common_metadata", {})
    extra_meta = common_meta.get("extra_metadata", {})

    # ---- Resolve technology fields ----
    platform_id = raw.get("platform_id") or _first(extra_meta.get("platform_id"))
    instrument_model = (
        common_meta.get("instrument_model")
        or _first(extra_meta.get("instrument_model"))
    )
    library_strategy = (
        _first(extra_meta.get("library_strategy"))
        or common_meta.get("library_strategy")
    )

    # ---- Build study semantic ----
    study_json = {
        "gse_id": gse_id,
        "title": title,
        "organism": organism,

        "study_summary": summary,

        "experimental_design": {
            "overall_design": _join(metadata.get("overall_design")),
            "experimental_type": _join(metadata.get("type")),
            "model_system": "iPSC-derived retinal organoids"
            if "organoid" in str(common_meta.get("tissue", "")).lower()
            else None,
            "tissue": common_meta.get("tissue"),
    
        },

        "sequencing_technology": {
            "platform_id": platform_id,
            "instrument_model": instrument_model,
            "library_strategy": library_strategy,
            "library_source": _join(extra_meta.get("library_source")),
            "library_selection": _join(extra_meta.get("library_selection")),
            "molecule": _join(extra_meta.get("molecule_ch1")),
            "channel_count": _first(extra_meta.get("channel_count")),
        },

        "experimental_protocols": {
            "growth_protocol": _join(extra_meta.get("growth_protocol_ch1")),
            "treatment_protocol": _join(extra_meta.get("treatment_protocol_ch1")),
            "extraction_protocol": extra_meta.get("extract_protocol_ch1"),
        },

        "data_processing": extra_meta.get("data_processing"),

        "study_metadata": {
            "status": _first(metadata.get("status")),
            "submission_date": _first(metadata.get("submission_date")),
            "last_update_date": _first(metadata.get("last_update_date")),
            "bioproject": _join(metadata.get("relation")),
        }
    }

    # ---- Cleanup nulls ----
    def clean(obj):
        if isinstance(obj, dict):
            return {k: clean(v) for k, v in obj.items() if v not in [None, "", [], {}]}
        return obj

    return clean(study_json)


def save_study_json(raw_json_path: str, output_dir: str):
    """
    Load raw GSE JSON and save study semantic JSON.
    """
    raw_json_path = Path(raw_json_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    with open(raw_json_path, "r", encoding="utf-8") as f:
        raw = json.load(f)

    study = generate_study_semantic(raw)

    out_path = output_dir / f"{study['gse_id']}.study.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(study, f, indent=2)

    print(f"✅ Study semantic JSON saved: {out_path}")


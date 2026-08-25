# ============================================================
# indexing/document_parser.py — Study + Sample JSON Parsers
# ============================================================
# DEPENDENCY INJECTION
#   parse_study_json() takes a `split_text_fn` callable
#   (text, parent_id) -> list[chunk] instead of importing the
#   chunker directly — this is a closure built in
#   scripts/run_indexing.py binding the tokenizer + chunk size
#   settings, so this module has no global dependencies.
# ============================================================

import json
from typing import Callable


# ============================================================
# Shared Helpers (used by parse_sample_json)
# ============================================================

def list_or_str_to_text(value) -> str:
    """Convert a value that may be a list or string into plain text."""
    if isinstance(value, list):
        return " ".join(str(item) for item in value if item is not None)
    if value is None:
        return ""
    return str(value)


def flatten_dict_to_text(data_dict: dict) -> str:
    """Flatten a dict of unpredictable keys into readable 'Key: value; ...' text."""
    if not isinstance(data_dict, dict) or not data_dict:
        return ""

    text_parts = []
    for key, value in data_dict.items():
        if value is None:
            continue
        readable_key = key.replace("_", " ").strip().title()
        text_parts.append(f"{readable_key}: {value}")

    return "; ".join(text_parts)


def normalize_url(url: str) -> str:
    """Fix protocol-relative URLs (//host/path) by prepending https:."""
    if not url:
        return ""
    if url.startswith("//"):
        return "https:" + url
    return url


# ============================================================
# Study Parser
# ============================================================

def parse_study_json(
    file_path     : str,
    split_text_fn : Callable[[str, str], list[dict]],
) -> list[dict]:
    """
    Parse a GEO study JSON file into child chunk documents.

    Args:
        file_path     : Full path to the study JSON file.
        split_text_fn : Callable(text, parent_id) -> list of
                        {"text", "parent_id", "child_index"} chunks.
                        Built in scripts/run_indexing.py as a
                        closure over the tokenizer + chunk size
                        settings (see indexing/chunker.py).

    Returns:
        List of child chunk documents: [{"text": str, "metadata": dict}, ...]
    """

    with open(file_path, "r", encoding="utf-8") as file:
        data = json.load(file)

    gse_id   = data.get("gse_id",   "")
    organism = data.get("organism", "")

    experimental_design = data.get("experimental_design", {})
    overall_design       = experimental_design.get("overall_design",    "")
    assay_type            = experimental_design.get("experimental_type", "")
    tissue                 = experimental_design.get("tissue",             "")
    model_system            = experimental_design.get("model_system",       "")

    sequencing_technology = data.get("sequencing_technology", {})
    platform_id            = sequencing_technology.get("platform_id",       "")
    instrument_model         = sequencing_technology.get("instrument_model",  "")
    library_strategy           = sequencing_technology.get("library_strategy", "")
    library_source               = sequencing_technology.get("library_source",   "")
    library_selection               = sequencing_technology.get("library_selection", "")
    molecule                         = sequencing_technology.get("molecule",          "")

    study_metadata    = data.get("study_metadata", {})
    submission_date    = study_metadata.get("submission_date",  "")
    last_update_date     = study_metadata.get("last_update_date", "")
    status                 = study_metadata.get("status",           "")

    # bioproject — accession-only (new) vs full URL (old format)
    bioproject_raw = study_metadata.get("bioproject", "")
    if bioproject_raw:
        if bioproject_raw.startswith("http"):
            bioproject_url = bioproject_raw
        else:
            bioproject_url = f"https://www.ncbi.nlm.nih.gov/bioproject/{bioproject_raw}"
    else:
        bioproject_url = ""

    # series_relationships — new section, fully optional
    series_rel        = data.get("series_relationships", {})
    is_superseries      = series_rel.get("is_superseries",   False)
    is_subseries          = series_rel.get("is_subseries",     False)
    parent_series_id        = series_rel.get("parent_series_id", "")
    subseries_ids             = series_rel.get("subseries_ids",    [])

    if not isinstance(subseries_ids, list):
        subseries_ids = []

    shared_metadata = {
        "level"             : "study",
        "gse_id"            : gse_id,
        "organism"          : organism,
        "assay_type"        : assay_type,
        "tissue"            : tissue,
        "platform_id"       : platform_id,
        "instrument_model"  : instrument_model,
        "library_strategy"  : library_strategy,
        "library_source"    : library_source,
        "library_selection" : library_selection,
        "molecule"          : molecule,
        "bioproject_url"    : bioproject_url,
        "submission_date"   : submission_date,
        "last_update_date"  : last_update_date,
        "status"            : status,
        "is_superseries"    : str(is_superseries).lower(),
        "is_subseries"      : str(is_subseries).lower(),
        "parent_series_id"  : parent_series_id,
        "subseries_ids"     : subseries_ids,
    }

    all_documents = []

    def create_chunks_for_field(field_name: str, field_text: str):
        if not field_text or not field_text.strip():
            return

        parent_id = f"{gse_id}_{field_name}"
        child_chunks = split_text_fn(field_text, parent_id)

        for chunk in child_chunks:
            all_documents.append({
                "text"     : chunk["text"],
                "metadata" : {
                    **shared_metadata,
                    "field"       : field_name,
                    "parent_id"   : chunk["parent_id"],
                    "child_index" : chunk["child_index"],
                },
            })

    # ── Core text fields ────────────────────────────────────
    create_chunks_for_field("title", data.get("title", ""))
    create_chunks_for_field("study_summary", data.get("study_summary", ""))
    create_chunks_for_field("overall_design", overall_design)

    # ── Experimental protocols ──────────────────────────────
    experimental_protocols = data.get("experimental_protocols", {})
    for protocol_name, protocol_content in experimental_protocols.items():
        if isinstance(protocol_content, list):
            protocol_content = " ".join(str(item) for item in protocol_content if item)
        elif not isinstance(protocol_content, str):
            protocol_content = str(protocol_content) if protocol_content else ""
        create_chunks_for_field(f"protocol_{protocol_name}", protocol_content)

    # ── Data processing ──────────────────────────────────────
    data_processing_steps = data.get("data_processing", [])
    if isinstance(data_processing_steps, list):
        data_processing_text = " ".join(str(step) for step in data_processing_steps if step)
    elif data_processing_steps:
        data_processing_text = str(data_processing_steps)
    else:
        data_processing_text = ""
    create_chunks_for_field("data_processing", data_processing_text)

    # ── Series relationships (NEW) ───────────────────────────
    relationship_text_parts = []

    if is_superseries and subseries_ids:
        relationship_text_parts.append(
            f"This is a SuperSeries composed of the following subseries: {', '.join(subseries_ids)}."
        )
    if is_subseries and parent_series_id:
        relationship_text_parts.append(
            f"This is a SubSeries belonging to parent series {parent_series_id}."
        )

    if relationship_text_parts:
        create_chunks_for_field("series_relationships", " ".join(relationship_text_parts))

    return all_documents


# ============================================================
# Sample Parser
# ============================================================

def parse_sample_json(file_path: str) -> list[dict]:
    """
    Parse a GEO sample JSON file into one document per sample.
    No study-level inheritance — every sample now carries its
    own organism and technical metadata directly.

    Args:
        file_path: Full path to the sample JSON file.

    Returns:
        List of sample documents: [{"text": str, "metadata": dict}, ...]
    """

    with open(file_path, "r", encoding="utf-8") as file:
        data = json.load(file)

    gse_id = data.get("gse_id", "")

    all_documents = []

    for sample in data.get("samples", []):

        gsm_id       = sample.get("gsm_id", "")
        sample_title = sample.get("title",  "")
        source_name  = sample.get("source_name", "")

        biological_metadata = sample.get("biological_metadata") or {}
        organism  = biological_metadata.get("organism",  "")
        strain    = biological_metadata.get("strain",    "")
        tissue    = biological_metadata.get("tissue",    "")
        specimen  = biological_metadata.get("specimen",  "")
        disease   = biological_metadata.get("disease",   "")
        genotype  = biological_metadata.get("genotype",  "")
        cell_line = biological_metadata.get("cell_line", "")
        cell_type = biological_metadata.get("cell_type", "")

        experimental_conditions      = sample.get("experimental_conditions") or {}
        experimental_conditions_text = flatten_dict_to_text(experimental_conditions)

        descriptions      = sample.get("descriptions", [])
        descriptions_text = list_or_str_to_text(descriptions)

        raw_extra_metadata      = sample.get("raw_extra_metadata") or {}
        raw_extra_metadata_text = flatten_dict_to_text(raw_extra_metadata)

        technical_metadata = sample.get("technical_metadata") or {}
        library_strategy    = technical_metadata.get("library_strategy",  "")
        instrument_model      = technical_metadata.get("instrument_model",  "")
        platform_id             = technical_metadata.get("platform_id",       "")

        sample_data_processing      = technical_metadata.get("data_processing", [])
        sample_data_processing_text = list_or_str_to_text(sample_data_processing)

        accessions    = sample.get("accessions") or {}
        biosample_url = normalize_url(accessions.get("biosample",      ""))
        sra_url        = normalize_url(accessions.get("sra_experiment", ""))

        text_lines = [f"Study: {gse_id}", f"Sample: {gsm_id}"]

        if sample_title:                 text_lines.append(f"Title: {sample_title}")
        if source_name:                  text_lines.append(f"Source: {source_name}")
        if organism:                      text_lines.append(f"Organism: {organism}")
        if strain:                         text_lines.append(f"Strain: {strain}")
        if tissue:                          text_lines.append(f"Tissue: {tissue}")
        if specimen:                         text_lines.append(f"Specimen: {specimen}")
        if disease:                           text_lines.append(f"Disease: {disease}")
        if genotype:                           text_lines.append(f"Genotype: {genotype}")
        if cell_line:                            text_lines.append(f"Cell Line: {cell_line}")
        if cell_type:                             text_lines.append(f"Cell Type: {cell_type}")
        if library_strategy:                      text_lines.append(f"Library Strategy: {library_strategy}")
        if instrument_model:                       text_lines.append(f"Instrument: {instrument_model}")
        if platform_id:                             text_lines.append(f"Platform: {platform_id}")
        if experimental_conditions_text:             text_lines.append(f"Experimental Conditions: {experimental_conditions_text}")
        if descriptions_text:                         text_lines.append(f"Description: {descriptions_text}")
        if raw_extra_metadata_text:                    text_lines.append(f"Additional Metadata: {raw_extra_metadata_text}")
        if sample_data_processing_text:                 text_lines.append(f"Data Processing: {sample_data_processing_text}")

        sample_text = "\n".join(text_lines)

        document = {
            "text"     : sample_text,
            "metadata" : {
                "level"       : "sample",
                "gse_id"      : gse_id,
                "gsm_id"      : gsm_id,
                "parent_id"   : gsm_id,
                "child_index" : 0,

                "organism"    : organism,
                "strain"      : strain,
                "source_name" : source_name,
                "title"       : sample_title,
                "tissue"      : tissue,
                "specimen"    : specimen,
                "disease"     : disease,
                "genotype"    : genotype,
                "cell_line"   : cell_line,
                "cell_type"   : cell_type,

                "library_strategy" : library_strategy,
                "instrument_model" : instrument_model,
                "platform_id"      : platform_id,

                "experimental_conditions_json" : json.dumps(experimental_conditions) if experimental_conditions else "",
                "raw_extra_metadata_json"      : json.dumps(raw_extra_metadata) if raw_extra_metadata else "",

                "biosample_url" : biosample_url,
                "sra_url"       : sra_url,
            },
        }

        all_documents.append(document)

    return all_documents

import json
import os
import uuid


def chunk_text(text, chunk_size=500):
    words = text.split()
    for i in range(0, len(words), chunk_size):
        yield " ".join(words[i:i+chunk_size])


 
def parse_study_json(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    gse_id = data["gse_id"]
    organism = data.get("organism")

    # -----------------------
    # Experimental Design
    # -----------------------
    exp_design = data.get("experimental_design", {})
    assay_type = exp_design.get("experimental_type")
    tissue = exp_design.get("tissue")

    # -----------------------
    # Sequencing Technology
    # -----------------------
    seq_tech = data.get("sequencing_technology", {})
    platform_id = seq_tech.get("platform_id")
    instrument_model = seq_tech.get("instrument_model")
    library_strategy = seq_tech.get("library_strategy")
    library_source = seq_tech.get("library_source")
    library_selection = seq_tech.get("library_selection")
    molecule = seq_tech.get("molecule")

    # -----------------------
    # Study Metadata (Payload Only)
    # -----------------------
    study_meta = data.get("study_metadata", {})
    bioproject_url = study_meta.get("bioproject")
    submission_date = study_meta.get("submission_date")
    last_update_date = study_meta.get("last_update_date")
    status = study_meta.get("status")

    documents = []

    # ===============================
    # 1️⃣ Core Study Text Embedding
    # ===============================
    core_fields = {
        "title": data.get("title", ""),
        "study_summary": data.get("study_summary", ""),
        "overall_design": exp_design.get("overall_design", "")
    }

    for field_name, content in core_fields.items():
        if content:
            for chunk in chunk_text(content):
                documents.append({
                    "text": chunk,
                    "metadata": {
                        "level": "study",
                        "gse_id": gse_id,
                        "field": field_name,
                        "organism": organism,
                        "assay_type": assay_type,
                        "tissue": tissue,
                        "platform_id": platform_id,
                        "instrument_model": instrument_model,
                        "library_strategy": library_strategy,
                        "library_source": library_source,
                        "library_selection": library_selection,
                        "molecule": molecule,
                        "bioproject_url": bioproject_url,
                        "submission_date": submission_date,
                        "last_update_date": last_update_date,
                        "status": status
                    }
                })

    # ===============================
    # 2️⃣ Experimental Protocols Embedding
    # ===============================
    protocols = data.get("experimental_protocols", {})

    for protocol_name, protocol_content in protocols.items():

        # Convert list to string
        if isinstance(protocol_content, list):
            protocol_content = " ".join(protocol_content)

        if protocol_content:
            for chunk in chunk_text(protocol_content):
                documents.append({
                    "text": chunk,
                    "metadata": {
                        "level": "study",
                        "gse_id": gse_id,
                        "field": f"protocol_{protocol_name}",
                        "organism": organism,
                        "assay_type": assay_type,
                        "tissue": tissue,
                        "platform_id": platform_id,
                        "instrument_model": instrument_model,
                        "library_strategy": library_strategy,
                        "library_source": library_source,
                        "library_selection": library_selection,
                        "molecule": molecule,
                        "bioproject_url": bioproject_url,
                        "submission_date": submission_date,
                        "last_update_date": last_update_date,
                        "status": status
                    }
                })

    # ===============================
    # 3️⃣ Data Processing Embedding
    # ===============================
    data_processing = data.get("data_processing", [])

    if isinstance(data_processing, list):
        data_processing = " ".join(data_processing)

    if data_processing:
        for chunk in chunk_text(data_processing):
            documents.append({
                "text": chunk,
                "metadata": {
                    "level": "study",
                    "gse_id": gse_id,
                    "field": "data_processing",
                    "organism": organism,
                    "assay_type": assay_type,
                    "tissue": tissue,
                    "platform_id": platform_id,
                    "instrument_model": instrument_model,
                    "library_strategy": library_strategy,
                    "library_source": library_source,
                    "library_selection": library_selection,
                    "molecule": molecule,
                    "bioproject_url": bioproject_url,
                    "submission_date": submission_date,
                    "last_update_date": last_update_date,
                    "status": status
                }
            })

    return documents


# Sample-level parsing 
def parse_sample_json(file_path, study_metadata_map):
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    gse_id = data["gse_id"]

    # 🔥 Inherit from study
    study_meta = study_metadata_map.get(gse_id, {})

    organism = study_meta.get("organism")
    assay_type = study_meta.get("assay_type")

    documents = []

    for sample in data.get("samples", []):
        gsm_id = sample["gsm_id"]

        bio = sample.get("biological_metadata", {})
        tech = sample.get("technical_metadata", {})
        accessions = sample.get("accessions", {})

        text = f"""
        Title: {sample.get('title')}
        Tissue: {bio.get('tissue')}
        Disease: {bio.get('disease')}
        genotype: {bio.get('genotype')}
        cell_line: {bio.get('cell_line')}   
        cell_type: {bio.get('cell_type')}
        Library strategy: {tech.get('library_strategy')}
        """

        documents.append({
            "text": text,
            "metadata": {
                "level": "sample",
                "gse_id": gse_id,
                "gsm_id": gsm_id,
                "organism": organism,        # 🔥 now inherited
                "assay_type": assay_type,
                "title": sample.get("title"),    # 🔥 now inherited
                "tissue": bio.get("tissue"),
                "disease": bio.get("disease"),
                "genotype": bio.get("genotype"),
                "cell_line": bio.get("cell_line"),
                "cell_type": bio.get("cell_type"),
                "biosample_url": accessions.get("biosample"),
                "sra_url": accessions.get("sra_experiment")
            }
        })

    return documents

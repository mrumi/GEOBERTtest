# ============================================================
# rag/answer_generator.py — Answer Generator
# ============================================================

from typing import Optional


def format_reranked_context_for_llm(reranked_context: list[dict], max_studies: int = 5) -> str:
    if not reranked_context:
        return "No relevant datasets were retrieved."

    evidence_lines = []

    for study_index, study in enumerate(reranked_context[:max_studies], 1):

        gse_id          = study.get("gse_id",          "")
        relevance_score = study.get("relevance_score", 0.0)
        metadata        = study.get("metadata",        {})
        fields          = study.get("fields",          {})

        geo_link = f"https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc={gse_id}" if gse_id else ""

        evidence_lines.append(f"--- Study {study_index}: {gse_id} ---")
        evidence_lines.append(f"GEO Link        : {geo_link}")
        evidence_lines.append(
            f"Relevance       : {round(relevance_score * 100, 1)}% "
            f"(model confidence this study matches the query)"
        )
        evidence_lines.append(f"Organism        : {metadata.get('organism',         '')}")
        evidence_lines.append(f"Tissue          : {metadata.get('tissue',           '')}")
        evidence_lines.append(f"Assay type      : {metadata.get('assay_type',       '')}")
        evidence_lines.append(f"Library strategy: {metadata.get('library_strategy', '')}")
        evidence_lines.append(f"Instrument      : {metadata.get('instrument_model', '')}")
        evidence_lines.append(f"BioProject      : {metadata.get('bioproject_url',   '')}")
        evidence_lines.append("")

        printed_fields = set()
        focus_field_order = [
            "title", "study_summary", "overall_design",
            "protocol_extraction_protocol", "protocol_growth_protocol",
            "protocol_treatment_protocol", "data_processing",
        ]

        for field_name in focus_field_order:
            if field_name in fields:
                evidence_lines.append(f"[{field_name}]:")
                evidence_lines.append(fields[field_name])
                evidence_lines.append("")
                printed_fields.add(field_name)

        for field_name, field_text in fields.items():
            if field_name not in printed_fields:
                evidence_lines.append(f"[{field_name}]:")
                evidence_lines.append(field_text)
                evidence_lines.append("")

        evidence_lines.append("=" * 60)
        evidence_lines.append("")

    return "\n".join(evidence_lines)


def format_sample_context_for_llm(sample_context: list[dict], max_samples: int = 15) -> str:
    if not sample_context:
        return "No sample-level (GSM) evidence was retrieved for this query."

    samples_by_gse: dict[str, list[dict]] = {}
    for hit in sample_context[:max_samples]:
        payload = hit.get("payload", {}) or {}
        gse_id  = payload.get("gse_id", "unknown")
        samples_by_gse.setdefault(gse_id, []).append(hit)

    lines = []

    for gse_id, hits in samples_by_gse.items():

        lines.append(f"--- Samples from {gse_id} ---")

        for hit in hits:
            payload = hit.get("payload", {}) or {}

            detail_parts = [
                f"GSM: {payload.get('gsm_id', '')}",
                f"Title: {payload.get('title')}" if payload.get("title") else None,
                f"Tissue: {payload.get('tissue')}" if payload.get("tissue") else None,
                f"Disease: {payload.get('disease')}" if payload.get("disease") else None,
                f"Genotype: {payload.get('genotype')}" if payload.get("genotype") else None,
                f"Cell line: {payload.get('cell_line')}" if payload.get("cell_line") else None,
                f"Cell type: {payload.get('cell_type')}" if payload.get("cell_type") else None,
            ]
            detail_parts = [p for p in detail_parts if p]

            lines.append("  " + " | ".join(detail_parts))

        lines.append("")

    return "\n".join(lines)


def format_dropped_filters(dropped_filters: dict) -> str:
    if not dropped_filters:
        return ""

    lines = ["The following query constraints were not found in the dataset collection:"]
    for field, value in dropped_filters.items():
        lines.append(f"  - {field}: '{value}' (no matching datasets found)")
    lines.append("Results shown are the closest available matches for the remaining constraints.")

    return "\n".join(lines)


def generate_answer(
    query             : str,
    query_info        : dict,
    reranked_context  : list[dict],
    groq_client,
    groq_answer_model : str,
    sample_context    : Optional[list[dict]] = None,
    dropped_filters   : Optional[dict] = None,
) -> str:
    """
    Generate a structured scientific answer using Groq LLM.

    Args:
        groq_client       : Groq client instance.
        groq_answer_model : settings.GROQ_ANSWER_MODEL.
        (other args unchanged from Cell 19)
    """

    if not reranked_context and not sample_context:
        return (
            "No relevant datasets were found for your query. "
            "This may be because the requested biological condition, "
            "tissue, or assay type is not present in the current dataset collection."
        )

    evidence_block        = format_reranked_context_for_llm(reranked_context)
    sample_evidence_block = format_sample_context_for_llm(sample_context or [])
    dropped_filters_text  = format_dropped_filters(dropped_filters or {})

    intent     = query_info.get("intent",     "find")
    operations = query_info.get("operations", [])
    query_type = query_info.get("query_type", "SEMANTIC")
    concepts   = query_info.get("concepts",   [])

    top_relevance = reranked_context[0].get("relevance_score", 0.0) if reranked_context else 0.0
    confidence_note = ""
    if top_relevance < 0.5:
        confidence_note = (
            "NOTE: The relevance scores for retrieved datasets are low "
            f"(top match confidence: {round(top_relevance * 100, 1)}%). "
            "The retrieved datasets may only partially match the query. "
            "Acknowledge this uncertainty clearly in your answer."
        )

    prompt = f"""<role>
You are GeoLLM, an expert biomedical research assistant specialized in
GEO (Gene Expression Omnibus) dataset discovery. You help researchers
find, evaluate, and understand genomics datasets through precise,
evidence-grounded answers.
</role>

<task>
Answer the researcher's query below using ONLY the retrieved evidence
provided. Your answer must be:
  - Directly responsive to what was asked
  - Grounded strictly in the evidence (no hallucination)
  - Concise and precise 
  - Written in fluent scientific English
  - Free of headers, bullet points, or section labels
</task>

<query>
{query}
</query>

<query_context>
Intent    : {intent}
Operations: {", ".join(operations)}
Query type: {query_type}
Concepts  : {", ".join(concepts)}
</query_context>

{f'''<unmatched_constraints>
{dropped_filters_text}
The following constraints were searched but not found in the collection.
Acknowledge this honestly in your answer without over-emphasizing it.
</unmatched_constraints>''' if dropped_filters_text else ""}

{f'''<confidence_note>
{confidence_note}
</confidence_note>''' if confidence_note else ""}

<retrieved_evidence>
<study_evidence>
{evidence_block}
</study_evidence>

<sample_evidence>
{sample_evidence_block}
</sample_evidence>
</retrieved_evidence>

<generation_instructions>
Step 1 — UNDERSTAND: Identify exactly what the researcher needs.
  Is it a list of datasets? A count? A specific experimental detail?
  A comparison? Match your answer format to what was asked.

Step 2 — SYNTHESIZE: Read all evidence chunks carefully.
  Identify which GSE IDs are most relevant. Cross-reference study-level
  text with sample-level metadata for specificity. Note what is present
  and what is absent.

Step 3 — GENERATE your answer following these rules:

  ALWAYS:
  - Mention relevant GSE IDs inline naturally ("GSE296973 contains...")
  - State the organism, tissue, and assay type when relevant to the query
  - Note the experimental comparison if present in the evidence
  - If multiple studies match, synthesize them ("Three studies examine...")
  - If evidence is partial, say exactly what IS found and what is NOT
  - Close with one sentence about missing information ONLY if meaningful

  NEVER:
  - Invent GSE IDs, GSM IDs, sample counts, or experimental details
  - Use section headers or numbered lists
  - Copy-paste raw evidence text verbatim
  - Speculate beyond what the evidence supports
  - Use vague phrases like "some studies" or "it appears" —
    be specific or state the evidence is insufficient
  - Include GEO URLs (the frontend renders these separately)

Step 4 — VERIFY: Before finalizing, confirm every factual claim
  in your answer appears explicitly in the retrieved evidence above.
  If a claim cannot be verified, remove it.
</generation_instructions>
"""

    response = groq_client.chat.completions.create(
        model       = groq_answer_model,
        messages    = [{"role": "user", "content": prompt}],
        temperature = 0.1,
        max_tokens  = 1800,               # you can adjust
    )

    return response.choices[0].message.content.strip()
from typing import List, Dict, Any
from collections import Counter


# build_authoritative_sample_summary
def build_authoritative_sample_summary(sample_context):
    """
    Compute deterministic sample counts from sample_context.
    LLM should report these numbers, not infer them.
    """
    summary = []

    for study in sample_context:
        gse_id = study.get("gse_id")
        mode = study.get("mode")
        total_samples = int(study.get("sample_count", 0))

        condition_counts = []

        if mode == "compressed_conditions":
            for cond in study.get("conditions", []):
                condition_counts.append({
                    "condition": cond.get("condition", "unknown"),
                    "replicates": int(cond.get("replicates", 0)),
                    "tissue": cond.get("tissue"),
                    "cell_line": cond.get("cell_line"),
                    "cell_type": cond.get("cell_type"),
                    "genotype": cond.get("genotype"),
                })

        elif mode == "full_samples":
            counter = Counter()
            meta_map = {}

            for s in study.get("samples", []):
                condition = (
                    s.get("genotype")
                    or s.get("cell_line")
                    or s.get("title")
                    or "unknown"
                )
                counter[condition] += 1

                if condition not in meta_map:
                    meta_map[condition] = {
                        "tissue": s.get("tissue"),
                        "cell_line": s.get("cell_line"),
                        "cell_type": s.get("cell_type"),
                        "genotype": s.get("genotype"),
                    }

            for condition, count in counter.items():
                condition_counts.append({
                    "condition": condition,
                    "replicates": int(count),
                    **meta_map[condition]
                })

        summary.append({
            "gse_id": gse_id,
            "total_samples": total_samples,
            "mode": mode,
            "condition_counts": condition_counts
        })

    return summary


# format_authoritative_sample_summary
def format_authoritative_sample_summary(sample_summary):
    lines = []

    for study in sample_summary:
        lines.append(f"Study {study['gse_id']} — Total samples: {study['total_samples']}")

        for cond in study.get("condition_counts", []):
            lines.append(
                f"Condition: {cond.get('condition')} | "
                f"Replicates: {cond.get('replicates')} | "
                f"Tissue: {cond.get('tissue')} | "
                f"Cell line: {cond.get('cell_line')} | "
                f"Cell type: {cond.get('cell_type')} | "
                f"Genotype: {cond.get('genotype')}"
            )

        lines.append("")

    return "\n".join(lines)


# format_context_for_llm
def format_context_for_llm(context: List[Dict[str, Any]], max_items: int = 10) -> str:
    """
    Formats retrieved context into structured evidence block.
    """
    lines = []

    for i, item in enumerate(context[:max_items], 1):
        lines.append(f"""
Evidence {i}:
Source: {item.get("source")}
GSE: {item.get("gse_id")}
GSM: {item.get("gsm_id")}
Field: {item.get("field")}
Organism: {item.get("organism")}
Tissue: {item.get("tissue")}
Assay: {item.get("assay_type")}
Score: {round(item.get("vector_score", 0), 3)}

Text:
{item.get("text")}
""")

    return "\n".join(lines)



# generate_answer
def generate_answer(
    query: str,
    retrieved_context: List[Dict[str, Any]],
    sample_context: List[Dict[str, Any]],
    groq_client,
    model: str = "llama-3.1-8b-instant"
) -> str:

    if not retrieved_context:
        return "No relevant datasets were found for this query."

    evidence_block = format_context_for_llm(retrieved_context)
    sample_summary = build_authoritative_sample_summary(sample_context)
    sample_block = format_authoritative_sample_summary(sample_summary)

    #print("\n===== AUTHORITATIVE SAMPLE SUMMARY =====\n")
    #print(sample_block)

    prompt = f"""
You are an expert biomedical research assistant specializing in GEO (Gene Expression Omnibus) datasets.
You help researchers explore GEO studies, understand experimental designs, and identify datasets relevant to their biological questions.

You are assisting biomedical researchers analyzing gene expression datasets.

Your responsibilities include:
- identifying datasets relevant to a biological hypothesis
- explaining the experimental design of GEO studies
- interpreting what biological questions the datasets can help answer
- highlighting how sample composition and experimental comparisons enable biological discovery

You may provide short scientific interpretation only when it is directly supported by the evidence.
Do not invent experimental details, results, sample counts, or comparisons.

Core rules:
- Answer only using the provided evidence.
- Do not hallucinate missing information.
- If the evidence is insufficient, clearly state the limitation.
- Do not infer experimental details that are not explicitly stated.
- Do not list datasets unless they clearly match the user query.
- Ignore irrelevant evidence.
- Write in a clear, scientific, polished, and conversational style suitable for researchers.

Formatting rules:
- Do not use markdown headings such as #, ##, or ###.
- Do not label sections as Step 1, Step 2, etc.
- Do not show chain-of-thought or reasoning process.
- Present the answer in a clean, reader-friendly structure with short section titles in plain text.
- Use simple labels such as: Key findings, Relevant datasets, Experimental details, Sample overview, Limitations.
- Keep the tone natural and professional, similar to a well-written research summary.
- Use bullet points only when they improve clarity.
- Do not add unnecessary formatting symbols.

Dataset reporting rules:
Only include datasets that are clearly supported by the evidence.
For each relevant dataset, include:
- GSE ID
- short description of the study
- why it matches the query
- supporting evidence text
- GEO link in this format:
  https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE_ID
- a brief note on what biological question the dataset can help investigate

When explaining a GEO dataset, identify whenever the evidence provides it:
- the biological condition or disease being investigated
- the experimental comparison
- the biological sample source
- the biological insight the dataset can help investigate

Experimental details:
Summarize the experimental design using only available metadata.
When present, include:
- organism
- assay type
- tissue or sample source
- sequencing technology
- library strategy
- relevant experimental procedures or analysis steps

Sample overview:

The "Authoritative Sample Summary" section contains precomputed sample counts generated directly from structured dataset metadata.

When reporting:
- total number of samples
- replicate counts
- control vs disease groups
- sample source (tissue or cell type)
- any relevant sample characteristics

You MUST use the numbers exactly as given in the Authoritative Sample Summary.

Do NOT recalculate, estimate, or infer sample counts from the study text or GSM list.
If the sample summary is present, it overrides any ambiguous wording in the evidence text.

When possible, briefly explain how the sample composition (number of samples, biological replicates, and experimental conditions) supports reliable differential expression or comparative analysis.


Desired answer style:
Start with a concise direct answer to the user’s query.
Then organize the response using these plain-text section labels when relevant:

Key findings
Relevant datasets
Experimental details
Sample overview
Limitations

Within each dataset entry, write in polished prose instead of rigid template-like output.
Avoid robotic phrasing.ble differential expression or comparative analysis.


User Query:
\"\"\"{query}\"\"\"

Authoritative Sample Summary:
{sample_block}

Retrieved Evidence:
{evidence_block}

"""

    response = groq_client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=1600,
    )

    return response.choices[0].message.content.strip()

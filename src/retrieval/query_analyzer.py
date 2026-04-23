"""
Query Analyzer

Responsible for:
1. LLM-based query interpretation
2. Metadata filter extraction
3. Grounding filters to dataset vocabulary
4. Confidence estimation
5. Retrieval strategy decision
"""

import json
import re
from difflib import SequenceMatcher
from typing import Dict, List, Iterable, Tuple, Optional

from src.system_init import groq_client


# -----------------------------
# Allowed Metadata Fields
# -----------------------------

DEFAULT_SCHEMA_FIELDS = [
    "organism",
    "tissue",
    "disease",
    "assay_type",
    "library_strategy",
    "library_source",
    "library_selection",
    "molecule",
    "instrument_model",
    "status",
    "genotype",
    "cell_line",
    "cell_type",
]


VALID_QUERY_TYPES = {
    "SEMANTIC",
    "METADATA",
    "MULTI_CONSTRAINT",
    "STUDY_DESIGN",
    "EXPERIMENTAL_PROTOCOL",
    "DATA_PROCESSING",
    "MODALITY",
    "PLATFORM",
}


# -----------------------------
# Utilities
# -----------------------------

def _norm(s: str) -> str:
    s = (s or "").strip().lower()
    s = s.replace("_", " ").replace("-", " ")
    s = re.sub(r"[^\w\s\+]", " ", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def _safe_json_load(text: str) -> Optional[dict]:
    if not text:
        return None

    text = text.strip()

    try:
        return json.loads(text)
    except Exception:
        pass

    m = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if not m:
        return None

    try:
        return json.loads(m.group(0))
    except Exception:
        return None


def _ratio(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


def _best_fuzzy_match(value: str, candidates: Iterable[str], cutoff: float = 0.86) -> Optional[Tuple[str, float]]:
    v = _norm(value)

    best = (None, 0.0)

    for c in candidates:
        sc = _ratio(v, c)

        if sc > best[1]:
            best = (c, sc)

    if best[0] is not None and best[1] >= cutoff:
        return best[0], best[1]

    return None


# -----------------------------
# LLM Query Parser
# -----------------------------

def llm_parse_query(query: str, groq_client, allowed_fields: List[str]) -> dict:

    schema_text = ", ".join(sorted(allowed_fields))

    prompt = f"""
You are a biomedical dataset query interpreter for GEO-style datasets.

Your task is to extract metadata filters and determine semantic search guidance.

Allowed metadata fields:
{schema_text}

Return STRICT JSON with this schema:

{{
  "query_type": "SEMANTIC|METADATA|MULTI_CONSTRAINT|STUDY_DESIGN|EXPERIMENTAL_PROTOCOL|DATA_PROCESSING|MODALITY|PLATFORM",

  "filters": {{
     "<field>": "<value>"
  }},

  "semantic_focus_fields": [
      "title",
      "study_summary",
      "experimental_design",
      "experimental_protocols",
      "data_processing"
  ],

  "requires_replicates": true/false,

  "logical_operator": "AND|OR|NOT|null"
}}

Rules:

• Extract metadata filters only when the query clearly specifies dataset properties 
  (organism, tissue, assay type, instrument, etc.).

• Do not invent metadata fields.

• Do not invent metadata values that are not supported by the query.

• If the query asks about biological mechanisms, diseases, or hypotheses → focus on "study_summary".

• If the query describes experimental comparisons or control vs treatment → focus on "experimental_design".

• If the query refers to lab procedures, treatments, or cell culture → focus on "experimental_protocols".

• If the query refers to computational analysis, alignment, software, pipelines, or output files → focus on "data_processing".

• If the query refers to study topic or research goal → include "title".

• semantic_focus_fields guide semantic retrieval but DO NOT restrict retrieval.

• When the organism appears as a common name, convert it to the scientific name used in GEO datasets.

Examples:
human → Homo sapiens
mouse → Mus musculus
rat → Rattus norvegicus

• Do not include null filters. If a field is not clearly present in the query, omit it.

Query:
\"\"\"{query}\"\"\"
"""

    resp = groq_client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
        max_tokens=350,
    )

    text = resp.choices[0].message.content.strip()

    parsed = _safe_json_load(text)

    if not isinstance(parsed, dict):

        return {
            "query_type": "SEMANTIC",
            "filters": {},
            "semantic_focus_fields": [],
            "requires_replicates": False,
            "logical_operator": None,
        }

    return parsed



# -----------------------------
# Metadata Grounding
# -----------------------------
def ground_and_repair_filters(
    filters: Dict[str, str],
    metadata_index: Dict[str, List[str]],
    allowed_fields: List[str],
    *,
    fuzzy_cutoff: float = 0.86,
):

    grounded = {}
    dropped = []
    reassigned = []

    if not filters:
        return grounded, dropped, reassigned, 1.0

    kept = 0
    grounded_count = 0

    normalized_index = {
        field: {_norm(v) for v in values}
        for field, values in metadata_index.items()
    }

    for field, raw_value in filters.items():

        if field not in allowed_fields:
            dropped.append({"field": field, "value": raw_value, "reason": "field_not_allowed"})
            continue

        kept += 1

        v = _norm(str(raw_value))

        vocab = normalized_index.get(field, set())

        if v in vocab:
            grounded[field] = v
            grounded_count += 1
            continue

        fm = _best_fuzzy_match(v, vocab, cutoff=fuzzy_cutoff)

        if fm:
            grounded[field] = fm[0]
            grounded_count += 1
            continue

        dropped.append({"field": field, "value": raw_value, "reason": "value_not_grounded"})

    value_grounding_conf = (grounded_count / kept) if kept > 0 else 1.0

    return grounded, dropped, reassigned, value_grounding_conf


# -----------------------------
# Confidence Scoring
# -----------------------------

def compute_confidence(
    *,
    parsed_ok: bool,
    returned_filter_count: int,
    allowed_filter_count: int,
    value_grounding_confidence: float,
):

    parse_conf = 0.95 if parsed_ok else 0.3

    schema_match_conf = (
        allowed_filter_count / returned_filter_count
        if returned_filter_count > 0 else 1.0
    )

    overall = (
        0.4 * parse_conf
        + 0.3 * schema_match_conf
        + 0.3 * value_grounding_confidence
    )

    return {
        "parse_confidence": round(parse_conf, 2),
        "schema_match_confidence": round(schema_match_conf, 2),
        "value_grounding_confidence": round(float(value_grounding_confidence), 2),
        "overall_confidence": round(float(overall), 2),
    }


# -----------------------------
# Retrieval Strategy Decision
# -----------------------------

def decide_strategy(conf: dict, filters: dict):

    # If no filters extracted → always semantic search
    if not filters:
        return "SEMANTIC_ONLY"

    c = float(conf.get("overall_confidence", 0.0))

    if c >= 0.85:
        return "HARD_FILTER"

    if c >= 0.60:
        return "SOFT_BOOST"

    return "SEMANTIC_ONLY"



# -----------------------------
# Unified Analyzer
# -----------------------------

def analyze_query(
    query: str,
    *,
    groq_client,
    metadata_index: Dict[str, List[str]],
    allowed_fields: List[str] = DEFAULT_SCHEMA_FIELDS,
):

    parsed = llm_parse_query(query, groq_client, allowed_fields)

    qtype = str(parsed.get("query_type", "SEMANTIC")).upper()

    if qtype not in VALID_QUERY_TYPES:
        qtype = "SEMANTIC"

    returned_filters = parsed.get("filters", {})
    semantic_focus_fields = parsed.get("semantic_focus_fields", [])

    grounded_filters, dropped, reassigned, val_ground_conf = ground_and_repair_filters(
        returned_filters,
        metadata_index,
        allowed_fields,
    )

    conf = compute_confidence(
        parsed_ok=True,
        returned_filter_count=len(returned_filters),
        allowed_filter_count=len(grounded_filters),
        value_grounding_confidence=val_ground_conf,
    )

    strategy = decide_strategy(conf, grounded_filters)

    return {
        "query_type": qtype,
        "filters": grounded_filters,
        "semantic_focus_fields": semantic_focus_fields,
        "requires_replicates": parsed.get("requires_replicates", False),
        "logical_operator": parsed.get("logical_operator", None),
        "confidence": conf,
        "strategy": strategy,
        "dropped_filters": dropped,
        "reassigned_filters": reassigned,
    }

# -----------------------------
# Standalone Test
# -----------------------------

'''if __name__ == "__main__":

    import json
    from pathlib import Path

    # Load metadata index generated during indexing
    metadata_path = Path("metadata/metadata_index.json")

    if not metadata_path.exists():
        raise FileNotFoundError(
            "metadata_index.json not found. Run indexing pipeline first."
        )

    with open(metadata_path) as f:
        metadata_index = json.load(f)

    queries = [
        "human retinal samples with mitochondrial dysfunction",
        "mouse brain samples sequenced on Illumina platform",
        "studies with single-cell RNA-seq of blood tissue",
        "datasets involving CD45+ immune cells",
        "GEO studies on Alzheimer's disease with replicates",
        "datasets involving matrix h5 processed files",
    ]

    for q in queries:

        print("\n" + "=" * 80)
        print("Analyzing query:", q)
        print("=" * 80)

        analysis = analyze_query(
            q,
            groq_client=groq_client,
            metadata_index=metadata_index,
            allowed_fields=DEFAULT_SCHEMA_FIELDS,
        )

        print(json.dumps(analysis, indent=2))'''

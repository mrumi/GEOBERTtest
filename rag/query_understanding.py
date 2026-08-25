# ============================================================
# rag/query_understanding.py — Merged LLM Query Understanding
# ============================================================
# Single LLM call that extracts everything needed from the
# user query in one shot.
# approach:
#   - One LLM call returns everything
#   - No vocabulary matching — ontology resolution handles it
#   - Simpler confidence based on filter count only
#   - Organism resolved via OrganismResolver
#
# Output structure:
#   {
#     "intent"               : "find | compare | explain | ...",
#     "operations"           : ["find", "compare"],
#     "query_type"           : "SEMANTIC | METADATA | ...",
#     "filters"              : {"organism": "mouse", "tissue": "blood"},
#     "concepts"             : ["PBMC", "single-cell", "diabetes"],
#     "semantic_focus_fields": ["title", "study_summary"],
#     "logical_operator"     : "AND | OR | NOT | null",
#     "resolved_organism"    : {...}  ← added after LLM call
#     "strategy"             : "HARD_FILTER | SOFT_BOOST | SEMANTIC_ONLY"
#     "confidence"           : 0.0 - 1.0
#   }
#      SESSION MEMORY IS USED.
#      so build_query_understanding_prompt() now accepts
#      session_memory and injects the previous turn's filters/
#      concepts as context, instructing the LLM to carry them
#      forward unless the current query explicitly overrides
#      them. The caller (api/routes/query.py) is
#      responsible for loading prior turns from the database
#      and building the session_memory list — this module only
#      consumes it.
# ============================================================

import json
import re
from typing import Optional


VALID_INTENTS = {
    "find", "compare", "explain", "identify",
    "list", "rank", "summarize", "describe"
}

VALID_QUERY_TYPES = {
    "SEMANTIC", "METADATA", "MULTI_CONSTRAINT", "STUDY_DESIGN",
    "EXPERIMENTAL_PROTOCOL", "DATA_PROCESSING", "MODALITY", "PLATFORM"
}

VALID_LOGICAL_OPERATORS = {"AND", "OR", "NOT", None}

ALLOWED_FILTER_FIELDS = [
    "organism", "tissue", "disease", "assay_type",
    "library_strategy", "library_source", "library_selection",
    "molecule", "instrument_model", "genotype",
    "cell_line", "cell_type", "status",
]

ALLOWED_FOCUS_FIELDS = [
    "title", "study_summary", "overall_design", "data_processing",
    "protocol_extraction_protocol", "protocol_growth_protocol",
    "protocol_treatment_protocol",
]


# ============================================================
# JSON Parser — Safe Extraction from LLM Response
# ============================================================

def extract_json_from_llm_response(response_text: str) -> Optional[dict]:
    """Safely extract a JSON object from an LLM response string."""
    if not response_text:
        return None

    text = response_text.strip()

    try:
        return json.loads(text)
    except Exception:
        pass

    code_block_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.DOTALL)
    if code_block_match:
        try:
            return json.loads(code_block_match.group(1))
        except Exception:
            pass

    brace_match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if brace_match:
        try:
            return json.loads(brace_match.group(0))
        except Exception:
            pass

    return None


# ============================================================
# Session Memory Formatter (NEW)
# ============================================================

def _format_session_memory_block(session_memory: Optional[list]) -> str:
    """
    Build the "conversation context" section of the prompt from
    the previous turn in this session, so the LLM can carry
    forward filters/concepts on follow-up queries.

    Args:
        session_memory: List of prior turns, each
                        {"query": str, "filters": dict, "concepts": list}.
                        Only the LAST turn is used — deeper history
                        is not injected to keep the prompt short and
                        because most follow-ups only reference the
                        immediately preceding turn.

    Returns:
        A prompt section string, or "" if no prior turns exist.
    """
    if not session_memory:
        return ""

    last_turn = session_memory[-1]

    return f"""
CONVERSATION CONTEXT (previous turn in this session):
  Previous query    : {last_turn.get("query", "")}
  Previous filters  : {json.dumps(last_turn.get("filters", {}))}
  Previous concepts : {json.dumps(last_turn.get("concepts", []))}

If the CURRENT query is a follow-up that does not restate constraints
explicitly (e.g. "same but for mouse", "what about ATAC-seq instead",
"now show me the samples"), CARRY FORWARD the previous filters/concepts
and only change what the current query explicitly asks to change.
If the current query introduces a completely unrelated topic, ignore
the previous context and start fresh.
"""


# ============================================================
# LLM Prompt Builder
# ============================================================

def build_query_understanding_prompt(
    query          : str,
    session_memory : Optional[list] = None
) -> str:
    """
    Build the prompt for merged LLM query understanding.

    Args:
        query         : Raw user query string.
        session_memory: Prior turns in this session (see
                        _format_session_memory_block). None or
                        [] for the first turn of a session.

    Returns:
        Full prompt string to send to the LLM.
    """

    allowed_fields_text    = ", ".join(ALLOWED_FILTER_FIELDS)
    allowed_focus_text     = ", ".join(ALLOWED_FOCUS_FIELDS)
    valid_query_types_text = ", ".join(sorted(VALID_QUERY_TYPES))
    context_block          = _format_session_memory_block(session_memory)

    prompt = f"""You are a biomedical dataset query interpreter for GEO (Gene Expression Omnibus).
Your task is to analyze the user query and extract structured retrieval information.
Return ONLY a valid JSON object. No explanation, no markdown, no extra text.

JSON schema to return:
{{
    "intent": "<one of: find | compare | explain | identify | list | rank | summarize | describe>",
    "operations": ["<list of operations the user wants>"],
    "query_type": "<one of: {valid_query_types_text}>",
    "filters": {{
        "<field>": "<value>"
    }},
    "concepts": ["<list of key biomedical concepts>"],
    "semantic_focus_fields": ["<list of GEO fields most relevant>"],
    "logical_operator": "<AND | OR | NOT | null>"
}}

=== RULES FOR EACH FIELD ===

intent:
  Primary goal: "find" for discovery, "compare" for comparison,
  "explain" for mechanisms, "summarize" for overview.

operations:
  All actions implied: ["find", "filter"] or ["compare", "identify"] etc.

query_type:
  SEMANTIC            — general biological question, no specific metadata
  METADATA            — mainly about metadata fields
  MULTI_CONSTRAINT    — multiple specific biological constraints
  STUDY_DESIGN        — experimental design or comparisons
  EXPERIMENTAL_PROTOCOL — lab procedures, treatments, cell culture
  DATA_PROCESSING     — computational analysis, alignment, software
  MODALITY            — sequencing technology or assay type
  PLATFORM            — specific sequencing platform or instrument

filters:
  Allowed fields: {allowed_fields_text}

  ORGANISM RULE:
    Extract when user mentions any species name (common or scientific).
    Always extract the raw term — the system resolves it to canonical
    scientific name separately.
    Examples: "human" → organism: "human"
              "mouse" → organism: "mouse"
              "Homo sapiens" → organism: "Homo sapiens"

  TISSUE RULE:
    Extract when user mentions a tissue, organ, or anatomical location.
    Use the term as stated — do not expand or normalize.
    Examples: "retina", "peripheral blood", "bone marrow", "liver"

  DISEASE RULE — READ CAREFULLY:
    Extract ONLY when the user mentions a SPECIFIC named medical condition.
    The value must be an actual disease name, NOT a generic word.

    VALID examples (real disease names):
      "diabetes"          → disease: "diabetes"
      "AMD"               → DO NOT extract as disease — add to concepts instead
      "age-related macular degeneration" → disease: "age-related macular degeneration"
      "preeclampsia"      → disease: "preeclampsia"
      "breast cancer"     → disease: "breast cancer"
      "Parkinson's disease" → disease: "Parkinson's disease"

    INVALID — DO NOT extract these as disease:
      "disease"           → generic word, not a disease name — omit entirely
      "condition"         → generic word — omit entirely
      "case"              → generic word — omit entirely
      "disorder"          → generic word — omit entirely
      "control vs disease" → "disease" here is generic — omit disease filter
      "sick"              → generic — omit

    For disease acronyms (AMD, ALS, PD, MS, IBD, AD):
      Do NOT extract as a filter — Qdrant metadata rarely stores acronyms.
      Instead add the EXPANDED form to concepts list so semantic retrieval
      finds it in study_summary text.
      Example: "AMD datasets" → concepts: ["age-related macular degeneration",
                                            "AMD", "macular degeneration"]
                              → NO disease filter

  LIBRARY_STRATEGY RULE — READ CAREFULLY:
    GEO stores library_strategy using SRA standard values.
    You MUST normalize user terms to GEO/SRA standard values.

    Normalization table (user term → GEO stored value):
      "RNA-seq", "RNA sequencing", "bulk RNA-seq",
      "transcriptomics", "gene expression sequencing"
                                    → "RNA-Seq"

      "scRNA-seq", "single-cell RNA-seq", "single cell RNA sequencing",
      "snRNA-seq", "single nucleus RNA-seq", "10x RNA-seq",
      "single-cell transcriptomics"
                                    → "RNA-Seq"
      NOTE: scRNA-seq is stored as RNA-Seq in GEO. The single-cell
      specificity lives in library_source field. Always normalize to
      "RNA-Seq" and add "single-cell" to concepts for semantic retrieval.

      "ATAC-seq", "chromatin accessibility", "open chromatin"
                                    → "ATAC-seq"

      "ChIP-seq", "chromatin immunoprecipitation"
                                    → "ChIP-Seq"

      "WGBS", "whole genome bisulfite", "methylation sequencing"
                                    → "Bisulfite-Seq"

      "Hi-C", "3D genome", "chromatin conformation"
                                    → "Hi-C"

      "WGS", "whole genome sequencing"
                                    → "WGS"

      "WES", "whole exome sequencing", "exome sequencing"
                                    → "WXS"

      "spatial transcriptomics", "Visium", "spatial RNA-seq"
                                    → "RNA-Seq"
      NOTE: add "spatial transcriptomics" to concepts for semantic retrieval.

      "microarray", "gene chip", "expression array"
                                    → DO NOT extract as library_strategy
      NOTE: microarray is a platform type, not an SRA library strategy.
      Add "microarray" to concepts instead.

  INSTRUMENT_MODEL RULE:
    Extract when user mentions a SPECIFIC sequencing instrument.
    DO NOT extract platform/chemistry names as instrument_model.

    VALID (actual instrument names):
      "NovaSeq 6000"     → instrument_model: "Illumina NovaSeq 6000"
      "HiSeq 2000"       → instrument_model: "Illumina HiSeq 2000"
      "NextSeq 500"      → instrument_model: "Illumina NextSeq 500"
      "PacBio Sequel"    → instrument_model: "PacBio Sequel"

    INVALID — add to concepts instead, NOT instrument_model:
      "10x Chromium"     → NOT an instrument — add to concepts
      "10x Genomics"     → NOT an instrument — add to concepts
      "Illumina"         → too vague — add to concepts
      "Oxford Nanopore"  → add to concepts unless specific model named

  GENERAL FILTER RULE:
    If a field is not clearly stated in the query, DO NOT invent it.
    Never extract null, empty string, or placeholder values.
    When uncertain whether a term fits a filter field, add it to
    concepts instead — semantic retrieval will handle it.

concepts:
  Key biomedical terms for semantic retrieval.
  Include: disease names, cell types, biological processes,
  gene names, pathway names, experimental conditions, acronyms.
  Always expand disease acronyms here even if not extracted as filter.
  Examples: ["PBMC", "age-related macular degeneration", "AMD",
             "photoreceptor", "CRISPR knockout", "autophagy"]

semantic_focus_fields:
  GEO text fields most relevant to this query.
  Allowed: {allowed_focus_text}
  - title                        : study topic or research goal
  - study_summary                : biological mechanisms or disease
  - overall_design               : experimental comparisons or design
  - data_processing              : computational pipeline or software
  - protocol_extraction_protocol : sample preparation or RNA extraction
  - protocol_growth_protocol     : cell culture or growth conditions
  - protocol_treatment_protocol  : treatments or experimental conditions
  Include 2-3 fields typically.

logical_operator:
  AND  — all filters must match (default for multi-constraint)
  OR   — any filter can match
  NOT  — exclude results matching filters
  null — single filter or no filters
{context_block}
User Query:
\"\"\"{query}\"\"\"
"""

    return prompt.strip()


# ============================================================
# Query Understanding — Main Function
# ============================================================

def analyze_query(
    query             : str,
    groq_client,
    organism_resolver,
    groq_query_model  : str,
    session_memory    : Optional[list] = None,
) -> dict:
    """
    Analyze a user query using a single merged LLM call.

    Args:
        query             : Raw user query string.
        groq_client       : Groq client instance (core/clients.py AppClients).
        organism_resolver : OrganismResolver instance (rag/organism_resolver.py).
        groq_query_model  : Model name for query understanding
                            (settings.GROQ_QUERY_MODEL).
        session_memory    : Prior turns in this session, for multi-turn
                            follow-up handling. See
                            _format_session_memory_block.

    Returns:
        Dict containing all query understanding output — see
        module docstring for schema.
    """

    prompt = build_query_understanding_prompt(query, session_memory=session_memory)

    try:
        llm_response = groq_client.chat.completions.create(
            model    = groq_query_model,
            messages = [{"role": "user", "content": prompt}],
            temperature = 0,
            max_tokens  = 1500,
            reasoning_effort = "low",
        )
        response_text = (llm_response.choices[0].message.content or "").strip()

        if not response_text:
            print(f"  [empty response] finish_reason={llm_response.choices[0].finish_reason}")
            return _build_fallback_query_info(query)

    except Exception as error:
        print(f"  [llm error] {error}")
        return _build_fallback_query_info(query)

    parsed = extract_json_from_llm_response(response_text)

    if not isinstance(parsed, dict):
        print(f"  [parse error] Could not extract JSON from LLM response")
        print(f"  Raw response: {response_text[:200]}")
        return _build_fallback_query_info(query)

    intent = str(parsed.get("intent", "find")).lower()
    if intent not in VALID_INTENTS:
        intent = "find"

    operations = parsed.get("operations", [])
    if not isinstance(operations, list):
        operations = [str(operations)]

    query_type = str(parsed.get("query_type", "SEMANTIC")).upper()
    if query_type not in VALID_QUERY_TYPES:
        query_type = "SEMANTIC"

    raw_filters = parsed.get("filters", {})
    if not isinstance(raw_filters, dict):
        raw_filters = {}

    filters = {
        field: value
        for field, value in raw_filters.items()
        if field in ALLOWED_FILTER_FIELDS
        and value
        and str(value).strip()
    }

    concepts = parsed.get("concepts", [])
    if not isinstance(concepts, list):
        concepts = []
    concepts = [str(c).strip() for c in concepts if c]

    focus_fields = parsed.get("semantic_focus_fields", [])
    if not isinstance(focus_fields, list):
        focus_fields = []

    semantic_focus_fields = [f for f in focus_fields if f in ALLOWED_FOCUS_FIELDS]

    if not semantic_focus_fields:
        semantic_focus_fields = ["title", "study_summary"]

    logical_operator = parsed.get("logical_operator", None)
    if logical_operator not in VALID_LOGICAL_OPERATORS:
        logical_operator = "AND" if len(filters) > 1 else None

    # ── Organism Resolution ─────────────────────────────────
    resolved_organism = None
    organism_term      = filters.get("organism", "")

    if organism_term:
        resolved_organism = organism_resolver.resolve_organism(organism_term)
        if resolved_organism and resolved_organism.get("source") != "unresolved":
            filters["organism"] = resolved_organism["canonical_name"]

    strategy   = _decide_strategy(filters, query_type)
    confidence = _compute_confidence(filters, parsed)

    return {
        "raw_query"            : query,
        "intent"               : intent,
        "operations"           : operations,
        "query_type"           : query_type,
        "filters"              : filters,
        "concepts"             : concepts,
        "semantic_focus_fields": semantic_focus_fields,
        "logical_operator"     : logical_operator,
        "resolved_organism"    : resolved_organism,
        "strategy"             : strategy,
        "confidence"           : confidence,
    }


def _decide_strategy(filters: dict, query_type: str) -> str:
    filter_count = len(filters)
    if filter_count >= 2:
        return "HARD_FILTER"
    if filter_count == 1:
        return "SOFT_BOOST"
    return "SEMANTIC_ONLY"


def _compute_confidence(filters: dict, parsed: dict) -> float:
    score = 0.0

    filter_count = len(filters)
    if filter_count >= 3:
        score += 0.5
    elif filter_count == 2:
        score += 0.4
    elif filter_count == 1:
        score += 0.25

    concepts = parsed.get("concepts", [])
    if isinstance(concepts, list) and len(concepts) >= 2:
        score += 0.3
    elif isinstance(concepts, list) and len(concepts) == 1:
        score += 0.15

    focus = parsed.get("semantic_focus_fields", [])
    if isinstance(focus, list) and len(focus) >= 1:
        score += 0.2

    return round(min(score, 1.0), 2)


def _build_fallback_query_info(query: str) -> dict:
    return {
        "raw_query"            : query,
        "intent"               : "find",
        "operations"           : ["find"],
        "query_type"           : "SEMANTIC",
        "filters"              : {},
        "concepts"             : [],
        "semantic_focus_fields": ["title", "study_summary"],
        "logical_operator"     : None,
        "resolved_organism"    : None,
        "strategy"             : "SEMANTIC_ONLY",
        "confidence"           : 0.0,
    }
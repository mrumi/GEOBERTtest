# ============================================================
# rag/organism_resolver.py — Organism Resolver (NCBI Taxonomy)
# ============================================================
# Resolves organism names from user queries into canonical
# scientific names using NCBI Taxonomy database.
#
# Why organism only:
#   - Users type organisms imprecisely ("mouse", "human")
#   - GEO metadata stores scientific names ("Mus musculus")
#   - Exact payload match needs canonical scientific name
#   - NCBI Taxonomy is 100% accurate for this purpose
#   - Other fields (tissue, disease) are handled by semantic
#     retrieval — no ontology resolution needed for them
#
# Design decisions:
#   - NCBI Taxonomy only — no EBI OLS
#   - SQLite cache — no re-fetching on notebook restart
#   - Retry + exponential backoff — handles network hiccups
#   - Uses "organism" field from LLM parsed filters directly
#   - esummary endpoint — reliable JSON (efetch returns XML)
# ============================================================

import sqlite3
import requests
import json
import time
from datetime import datetime
from typing import Optional


# ============================================================
# SQLite Cache
# ============================================================

class OrganismCache:
    """
    SQLite-backed cache for resolved organism names.
    Persists across process restarts.
    """

    def __init__(self, database_path: str):
        self.database_path = database_path
        self._create_table_if_not_exists()

    def _create_table_if_not_exists(self):
        with sqlite3.connect(self.database_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS organism_cache (
                    term          TEXT PRIMARY KEY,
                    resolved_json TEXT NOT NULL,
                    created_at    TEXT NOT NULL
                )
            """)
            conn.commit()

    def get(self, term: str) -> Optional[dict]:
        normalized = term.strip().lower()
        with sqlite3.connect(self.database_path) as conn:
            cursor = conn.execute(
                "SELECT resolved_json FROM organism_cache WHERE term = ?",
                (normalized,)
            )
            row = cursor.fetchone()
        return json.loads(row[0]) if row else None

    def set(self, term: str, resolved: dict):
        normalized = term.strip().lower()
        timestamp  = datetime.now().isoformat()
        with sqlite3.connect(self.database_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO organism_cache
                    (term, resolved_json, created_at)
                VALUES (?, ?, ?)
            """,
            (normalized, json.dumps(resolved), timestamp))
            conn.commit()

    def get_all_cached_terms(self) -> list[str]:
        with sqlite3.connect(self.database_path) as conn:
            cursor = conn.execute("SELECT term FROM organism_cache ORDER BY term")
            return [row[0] for row in cursor.fetchall()]

    def get_size(self) -> int:
        with sqlite3.connect(self.database_path) as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM organism_cache")
            return cursor.fetchone()[0]


# ============================================================
# NCBI Taxonomy Resolver
# ============================================================

class OrganismResolver:
    """
    Resolves organism names to canonical scientific names
    using NCBI Taxonomy via esummary (JSON endpoint).
    """

    NCBI_ESEARCH_URL  = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    NCBI_ESUMMARY_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"

    MAX_RETRIES      = 3
    RETRY_BASE_DELAY = 1.0
    REQUEST_TIMEOUT  = 8

    # Common organism names to pre-warm at startup. Kept here
    # (rather than in a caller) since it's a fixed, resolver-
    # specific list — call resolver.prewarm_common_organisms()
    # once at app startup, not automatically at import time.
    COMMON_ORGANISMS = [
        "human", "mouse", "rat", "zebrafish",
        "fruit fly", "worm", "yeast", "pig",
        "rabbit", "chicken", "macaque", "hamster",
        "Homo sapiens", "Mus musculus", "Rattus norvegicus",
        "Danio rerio", "Drosophila melanogaster",
        "Caenorhabditis elegans", "Saccharomyces cerevisiae",
        "Sus scrofa", "Gallus gallus", "Oryctolagus cuniculus",
        "Macaca mulatta", "Xenopus laevis",
    ]

    def __init__(self, cache_database_path: str):
        self.cache = OrganismCache(cache_database_path)
        print(f"OrganismResolver initialized. Cached terms: {self.cache.get_size()}")

    def prewarm_common_organisms(self) -> None:
        """
        Resolve COMMON_ORGANISMS once so they're served instantly
        from cache thereafter. Call this exactly once at app
        startup — see main.py lifespan hook.
        """
        print("Pre-warming organism cache...")
        for organism in self.COMMON_ORGANISMS:
            self.resolve_organism(organism)
        print(f"Cache size after pre-warming: {self.cache.get_size()} terms")

    def resolve_organism(self, organism_term: str) -> dict:
        """
        Resolve a single organism term to its canonical name.

        Returns:
            {
                "canonical_name": str, "taxonomy_id": str|None,
                "common_name": str, "ontology_id": str|None,
                "source": "ncbi_taxonomy" | "unresolved"
            }
        """
        if not organism_term or not organism_term.strip():
            return self._build_fallback(organism_term or "")

        cached = self.cache.get(organism_term)
        if cached:
            return cached

        taxonomy_id = self._search_ncbi_taxonomy(organism_term)
        if not taxonomy_id:
            fallback = self._build_fallback(organism_term)
            self.cache.set(organism_term, fallback)
            return fallback

        resolved = self._fetch_ncbi_summary(taxonomy_id, organism_term)
        if not resolved:
            fallback = self._build_fallback(organism_term)
            self.cache.set(organism_term, fallback)
            return fallback

        self.cache.set(organism_term, resolved)
        return resolved

    def resolve_from_filters(self, filters: dict) -> Optional[dict]:
        organism_term = filters.get("organism", "")
        if not organism_term:
            return None
        return self.resolve_organism(organism_term)

    def _search_ncbi_taxonomy(self, term: str) -> Optional[str]:
        for attempt in range(1, self.MAX_RETRIES + 1):
            try:
                response = requests.get(
                    self.NCBI_ESEARCH_URL,
                    params  = {"db": "taxonomy", "term": term, "retmode": "json", "retmax": 1},
                    timeout = self.REQUEST_TIMEOUT
                )
                if response.status_code != 200:
                    raise ValueError(f"HTTP {response.status_code} from NCBI esearch")

                data    = response.json()
                id_list = data.get("esearchresult", {}).get("idlist", [])
                if id_list:
                    return id_list[0]
                return None

            except Exception as error:
                wait_seconds = self.RETRY_BASE_DELAY * (2 ** (attempt - 1))
                print(f"    [ncbi esearch attempt {attempt}/{self.MAX_RETRIES}] {error} — retrying in {wait_seconds:.1f}s")
                if attempt < self.MAX_RETRIES:
                    time.sleep(wait_seconds)
        return None

    def _fetch_ncbi_summary(self, taxonomy_id: str, original_term: str) -> Optional[dict]:
        for attempt in range(1, self.MAX_RETRIES + 1):
            try:
                response = requests.get(
                    self.NCBI_ESUMMARY_URL,
                    params  = {"db": "taxonomy", "id": taxonomy_id, "retmode": "json"},
                    timeout = self.REQUEST_TIMEOUT
                )
                if response.status_code != 200:
                    raise ValueError(f"HTTP {response.status_code} from NCBI esummary")

                data         = response.json()
                result_block = data.get("result", {})
                taxon_info   = result_block.get(taxonomy_id, {})

                if not isinstance(taxon_info, dict):
                    return None

                canonical_name = taxon_info.get("scientificname", "")
                if not canonical_name:
                    return None

                common_name = taxon_info.get("commonname", "")

                return {
                    "canonical_name" : canonical_name,
                    "taxonomy_id"    : taxonomy_id,
                    "common_name"    : common_name,
                    "ontology_id"    : f"NCBITaxon:{taxonomy_id}",
                    "source"         : "ncbi_taxonomy"
                }

            except Exception as error:
                wait_seconds = self.RETRY_BASE_DELAY * (2 ** (attempt - 1))
                print(f"    [ncbi esummary attempt {attempt}/{self.MAX_RETRIES}] {error} — retrying in {wait_seconds:.1f}s")
                if attempt < self.MAX_RETRIES:
                    time.sleep(wait_seconds)
        return None

    def _build_fallback(self, term: str) -> dict:
        return {
            "canonical_name" : term,
            "taxonomy_id"    : None,
            "common_name"    : "",
            "ontology_id"    : None,
            "source"         : "unresolved"
        }
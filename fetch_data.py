import sqlite3
import json
import os
import re
import requests
import pandas as pd
from io import StringIO
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
import time
from GEOparse import get_GEO
from tqdm import tqdm

DB_PATH = "/content/geo_data.db"


# ---------------------- DB Init ----------------------
def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS gse (
        gse_id TEXT PRIMARY KEY,
        title TEXT,
        organism TEXT,
        summary TEXT,
        sample_ids TEXT,
        supplementary_files TEXT,
        platform_id TEXT,
        metadata_json TEXT,
        PRJNA_RUN_METADATA TEXT
    );
    """)

    conn.commit()
    conn.close()
    print("✅ Database initialized successfully!")


# ---------------------- Helpers ----------------------
def safe_get(d, key, default=None):
    return d.get(key, [default])[0] if isinstance(d.get(key), list) else d.get(key, default)


def extract_bioproject(gse):
    relations = gse.metadata.get("relation", [])
    if not relations:
        return None
    for r in relations:
        match = re.search(r"(PRJNA\d+)", r)
        if match:
            return match.group(1)
    return None


def get_organism(gse):
    if "organism" in gse.metadata:
        orgs = gse.metadata["organism"]
        return ";".join(sorted(set(orgs))) if isinstance(orgs, list) else orgs

    organisms = set()
    for gsm in gse.gsms.values():
        if "organism_ch1" in gsm.metadata:
            val = gsm.metadata["organism_ch1"]
            organisms.update(val if isinstance(val, list) else [val])

    return ";".join(sorted(organisms)) if organisms else None


# ---------------------- PRJNA Metadata ----------------------
def get_llm_metadata_filtered(accession_id):
    print(f"Fetching FULL (unfiltered) metadata for Accession: {accession_id}...\n")

    all_runs_metadata = []

    try:
        # ESEARCH
        esearch_url = (
            f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
            f"?db=sra&term={accession_id}&usehistory=y"
        )
        time.sleep(1)
        esearch_response = requests.get(esearch_url, timeout=15)
        esearch_response.raise_for_status()

        soup = BeautifulSoup(esearch_response.text, 'xml')
        web_env = soup.find('WebEnv').text
        query_key = soup.find('QueryKey').text
        count = int(soup.find('Count').text)

        if count == 0:
            return {"Error": "No SRA runs found"}

        # EFETCH
        efetch_url = (
            f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
            f"?db=sra&query_key={query_key}&WebEnv={web_env}"
            f"&rettype=runinfo&retmode=text"
        )
        time.sleep(1)
        efetch_response = requests.get(efetch_url, timeout=30)
        efetch_response.raise_for_status()

        df = pd.read_csv(StringIO(efetch_response.text), sep=',')
        if df.empty:
            return {"Error": "RunInfo empty"}

        # Parse each run
        for _, run_series in df.iterrows():
            all_fields = {k: (str(v) if pd.notna(v) else "missing") for k, v in run_series.items()}

            biosample_id = all_fields.get("BioSample")

            if biosample_id and biosample_id.lower() != "missing":
                time.sleep(1)
                biosample_url = (
                    f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
                    f"?db=biosample&id={biosample_id}&rettype=xml"
                )
                xml_resp = requests.get(biosample_url, timeout=15)
                xml_resp.raise_for_status()

                root = ET.fromstring(xml_resp.text)
                for attr in root.findall(".//Attribute"):
                    key = attr.get("harmonized_name") or attr.get("attribute_name")
                    val = attr.text
                    if key and val:
                        cleaned_key = key.strip().replace(" ", "_").replace(":", "")
                        all_fields[cleaned_key] = val.strip()

            all_runs_metadata.append(all_fields)

    except Exception as e:
        return {"Error": str(e)}

    return all_runs_metadata


# ---------------------- Common + Specific Split ----------------------
def merge_dicts(dicts):
    if not dicts:
        return {}
    common = {}
    keys = set().union(*[d.keys() for d in dicts])
    for key in keys:
        values = [d.get(key) for d in dicts]
        if all(v == values[0] for v in values):
            common[key] = values[0]
        elif all(isinstance(v, dict) for v in values):
            nested = merge_dicts(values)
            if nested:
                common[key] = nested
    return common


def remove_common(sample, common):
    result = {}
    for k, v in sample.items():
        if k not in common:
            result[k] = v
        elif isinstance(v, dict) and isinstance(common.get(k), dict):
            nested = remove_common(v, common[k])
            if nested:
                result[k] = nested
    return result


def split_common_vs_specific(sample_list):
    common = merge_dicts(sample_list)
    specific = [remove_common(s, common) for s in sample_list]
    return common, specific


# ---------------------- MAIN INGEST ----------------------
def ingest_gse_list(gse_list):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    for gse_id in tqdm(gse_list, desc="🔽 Downloading GSEs"):
        try:
            gse = get_GEO(geo=gse_id, destdir=None, silent=True)
            # ---------------- GSM LIST ----------------
            gsm_list = []

            for gsm_id, gsm in gse.gsms.items():

                gsm_title = safe_get(gsm.metadata, "title")
                organism = safe_get(gsm.metadata, "organism_ch1")

                tissue = timepoint = strain = None
                for ch in gsm.metadata.get("characteristics_ch1", []):
                    low = ch.lower()
                    if "tissue" in low:
                        tissue = ch.split(":")[-1].strip()
                    if "age" in low or "time" in low:
                        timepoint = ch.split(":")[-1].strip()
                    if "strain" in low:
                        strain = ch.split(":")[-1].strip()

                extra = {k: v for k, v in gsm.metadata.items()}

                gsm_list.append({
                    "gsm_id": gsm_id,
                    "title": gsm_title,
                    "organism": organism,
                    "tissue": tissue,
                    "timepoint": timepoint,
                    "strain": strain,
                    "platform_id": safe_get(gsm.metadata, "platform_id"),
                    "instrument_model": safe_get(gsm.metadata, "instrument_model"),
                    "library_strategy": safe_get(gsm.metadata, "library_strategy"),
                    "extra_metadata": extra
                })

            # ---- SPLIT GSM COMMON + SPECIFIC ----
            meta_only = [g.copy() for g in gsm_list]
            gsm_common, gsm_specific = split_common_vs_specific(meta_only)

            final_samples_json = json.dumps({
                "common_metadata": gsm_common,
                "samples_specific_metadata": gsm_specific
            })

            # ---------------- PRJNA METADATA ----------------
            bioproject_id = extract_bioproject(gse)
            prjna_meta_json = None

            if bioproject_id:
                prjna_raw = get_llm_metadata_filtered(bioproject_id)

                if isinstance(prjna_raw, list) and len(prjna_raw) > 0:
                    prjna_common, prjna_specific = split_common_vs_specific(prjna_raw)

                    prjna_meta_json = json.dumps({
                        "common_metadata": prjna_common,
                        "runs_specific_metadata": prjna_specific
                    })
                else:
                    prjna_meta_json = json.dumps({"Error": "No PRJNA metadata"})

            # ---------------- GSE EXTRA META ----------------
            extra_meta = {}
            for k, v in gse.metadata.items():
                if k not in ["title", "organism", "summary", "sample_id",
                             "supplementary_file", "platform_id", "geo_accession"]:
                    extra_meta[k] = v

            gse_meta_json = json.dumps(extra_meta)

            # ---------------- INSERT INTO DB ----------------
            cur.execute("""
                INSERT OR REPLACE INTO gse
                (gse_id, title, organism, summary, sample_ids, supplementary_files,
                 platform_id, metadata_json, PRJNA_RUN_METADATA)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                gse_id,
                safe_get(gse.metadata, "title"),
                get_organism(gse),
                safe_get(gse.metadata, "summary"),
                final_samples_json,
                json.dumps(gse.metadata.get("supplementary_file", [])),
                ",".join(gse.metadata.get("platform_id", [])),
                gse_meta_json,
                prjna_meta_json
            ))

            conn.commit()

        except Exception as e:
            print(f"⚠️ Error: {e}")

    conn.close()

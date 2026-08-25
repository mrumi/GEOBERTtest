# ============================================================
# api/routes/datasets.py — Dataset Detail Lookup
# ============================================================
# Backs the "Details" in frontend
# dropdown on each result card in the frontend mockup — fetches
# everything Qdrant has for one GSE_ID directly (no retrieval/
# ranking involved, just a direct lookup by ID).
# ============================================================

from fastapi import APIRouter, Depends, HTTPException
from qdrant_client.models import Filter, FieldCondition, MatchValue

from core.config import Settings
from core.clients import AppClients
from api.dependencies import get_current_user, get_clients, get_settings
from models.user import User
from api.schemas import DatasetDetail, SampleResult

router = APIRouter(prefix="/datasets", tags=["datasets"])


@router.get("/{gse_id}", response_model=DatasetDetail)
async def get_dataset_detail(
    gse_id       : str,
    clients      : AppClients = Depends(get_clients),
    settings     : Settings = Depends(get_settings),
    current_user : User = Depends(get_current_user),
):
    """
    Fetch full study + sample detail for one GSE_ID directly
    from Qdrant, bypassing retrieval/ranking entirely — this is
    a lookup, not a search.
    """

    study_points, _ = clients.qdrant_client.scroll(
        collection_name = settings.STUDY_COLLECTION,
        scroll_filter    = Filter(must=[FieldCondition(key="gse_id", match=MatchValue(value=gse_id))]),
        limit            = 50,
        with_payload     = True,
        with_vectors     = False,
    )

    if not study_points:
        raise HTTPException(status_code=404, detail=f"No study found for {gse_id}")

    fields: dict[str, str] = {}
    top_payload = study_points[0].payload

    for point in study_points:
        payload    = point.payload
        field_name = payload.get("field", "unknown")
        text       = payload.get("text", "")
        # Concatenate chunks belonging to the same field, in order —
        # good enough for a detail view (not used for retrieval).
        fields[field_name] = (fields.get(field_name, "") + " " + text).strip()

    sample_points, _ = clients.qdrant_client.scroll(
        collection_name = settings.SAMPLE_COLLECTION,
        scroll_filter    = Filter(must=[FieldCondition(key="gse_id", match=MatchValue(value=gse_id))]),
        limit            = 500,
        with_payload     = True,
        with_vectors     = False,
    )

    samples = [
        SampleResult(
            gse_id   = p.payload.get("gse_id", ""),
            gsm_id   = p.payload.get("gsm_id", ""),
            tissue   = p.payload.get("tissue", ""),
            organism = p.payload.get("organism", ""),
            specimen = p.payload.get("specimen", ""),
            cell_line = p.payload.get("cell_line", ""),
            cell_type = p.payload.get("cell_type", ""),
            disease  = p.payload.get("disease", ""),
            genotype = p.payload.get("genotype", ""),
        )
        for p in sample_points
    ]

    return DatasetDetail(
        gse_id           = gse_id,
        geo_link         = f"https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc={gse_id}",
        organism         = top_payload.get("organism", ""),
        tissue           = top_payload.get("tissue", ""),
        assay_type       = top_payload.get("assay_type", ""),
        library_strategy = top_payload.get("library_strategy", ""),
        instrument_model = top_payload.get("instrument_model", ""),
        bioproject_url   = top_payload.get("bioproject_url", ""),
        fields           = fields,
        sample_count     = len(samples),
        samples          = samples,
        is_superseries   = str(top_payload.get("is_superseries", "false")).lower() == "true",
        is_subseries     = str(top_payload.get("is_subseries", "false")).lower() == "true",
        parent_series_id = top_payload.get("parent_series_id", ""),
        subseries_ids    = top_payload.get("subseries_ids", []) or [],
    )
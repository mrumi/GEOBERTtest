# ============================================================
# api/schemas.py — Request/Response Models
# ============================================================
# Defines the JSON contract
# between FastAPI and the frontend (React/HTML).
# ============================================================

import uuid
from datetime import datetime
from typing import Optional, Literal

from pydantic import BaseModel, EmailStr, Field


# ============================================================
# Auth
# ============================================================

UserRole = Literal["researcher", "clinician", "student", "admin"]


class UserRegister(BaseModel):
    full_name : str = Field(min_length=1, max_length=255)
    username  : str = Field(min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9_.-]+$")
    email     : EmailStr
    password  : str = Field(min_length=8)
    role      : UserRole = "researcher"


class UserOut(BaseModel):
    id        : uuid.UUID
    full_name : str
    username  : str
    email     : EmailStr
    role      : str
    created_at: datetime

    class Config:
        from_attributes = True


class UserLogin(BaseModel):
    email    : EmailStr
    password : str


class TokenResponse(BaseModel):
    access_token : str
    token_type   : str = "bearer"


# ============================================================
# Sessions
# ============================================================

class SessionSummary(BaseModel):
    id         : uuid.UUID
    title      : str
    created_at : datetime
    updated_at : datetime

    class Config:
        from_attributes = True


class MessageOut(BaseModel):
    role             : str
    content          : str
    query_info       : Optional[dict] = None
    dropped_filters  : Optional[dict] = None
    top_gse_ids      : Optional[list] = None
    studies          : Optional[list[dict]] = None
    samples          : Optional[list[dict]] = None
    dashboard_stats  : Optional[dict] = None
    created_at       : datetime

    class Config:
        from_attributes = True


class SessionDetail(BaseModel):
    id         : uuid.UUID
    title      : str
    created_at : datetime
    updated_at : datetime
    messages   : list[MessageOut]

    class Config:
        from_attributes = True


# ============================================================
# Query
# ============================================================

class QueryRequest(BaseModel):
    query      : str = Field(min_length=1)
    session_id : Optional[uuid.UUID] = None   # None -> create a new session


class StudyResult(BaseModel):
    gse_id          : str
    relevance_score : float   # 0-1, sigmoid-normalized 
    geo_link        : str
    organism        : str
    tissue          : str
    assay_type      : str
    library_strategy: str
    fields_found    : list[str]
    # Series relationships — shown only when present (frontend
    # should hide/collapse this section when both flags are False
    # and subseries_ids/parent_series_id are empty).
    is_superseries   : bool = False
    is_subseries      : bool = False
    parent_series_id  : str = ""
    subseries_ids      : list[str] = []



class SampleResult(BaseModel):
    gse_id           : str = ""
    gsm_id           : str = ""
    relevance_score  : Optional[float] = None
    title            : str = ""
    organism         : str = ""
    library_strategy : str = ""
    cell_line        : str = ""
    cell_type        : str = ""
    tissue           : str = ""
    disease          : str = ""
    genotype         : str = ""


class QueryResponse(BaseModel):
    session_id      : uuid.UUID
    query           : str
    answer          : str
    intent          : str
    query_type      : str
    strategy        : str
    filters         : dict
    dropped_filters : dict
    top_gse_ids     : list[str]
    studies         : list[StudyResult]
    samples         : list[SampleResult]
    dashboard_stats : dict   # see rag/result_aggregator.py::build_dashboard_stats() for exact shape


# ============================================================
# Dataset Detail
# ============================================================

class DatasetDetail(BaseModel):
    gse_id       : str
    geo_link     : str
    organism     : str
    tissue       : str
    assay_type   : str
    library_strategy : str
    instrument_model : str
    bioproject_url   : str
    fields       : dict[str, str]      
    sample_count : int
    samples      : list[SampleResult]
    is_superseries   : bool = False
    is_subseries      : bool = False
    parent_series_id  : str = ""
    subseries_ids      : list[str] = []
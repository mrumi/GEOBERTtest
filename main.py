# ============================================================
# main.py — FastAPI Application Entrypoint
# ============================================================

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.config import settings
from core.clients import AppClients
from rag.organism_resolver import OrganismResolver

from api.routes import auth, sessions, query, datasets


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Runs ONCE when the app starts (not per request). This is
    where every heavyweight, expensive-to-load thing happens —
    see core/clients.py's docstring for why this matters.
    """

    print("=== GeoBERT API starting up ===")

    settings.ensure_directories()

    # we use Alembic migrations instead (alembic/ folder)
    # so schema changes are tracked and reversible.
    

    app.state.clients = AppClients.load(settings)

    app.state.organism_resolver = OrganismResolver(
        cache_database_path=settings.ONTOLOGY_CACHE_DB
    )
    app.state.organism_resolver.prewarm_common_organisms()

    print("=== GeoBERT API ready ===")

    yield

    print("=== GeoBERT API shutting down ===")


app = FastAPI(
    title       = "GeoBERT API",
    description = "Biomedical GEO dataset search and Q&A over Qdrant + Groq",
    version     = "0.1.0",
    lifespan    = lifespan,
)

# CORS — required for the React/HTML frontend (running on a
# different origin/port during development) to call this API.
app.add_middleware(
    CORSMiddleware,
    allow_origins     = ["http://localhost:3000", "http://localhost:5173"],  # adjust for your frontend dev server
    allow_credentials = True,
    allow_methods     = ["*"],
    allow_headers     = ["*"],
)

app.include_router(auth.router)
app.include_router(sessions.router)
app.include_router(query.router)
app.include_router(datasets.router)


@app.get("/health")
async def health_check():
    return {"status": "ok"}
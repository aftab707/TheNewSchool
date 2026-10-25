"""
FastAPI application entrypoint for Smart CRM (Point d'entrée de l'application FastAPI pour Smart CRM).
Clean and minimal main file (Fichier principal épuré et modulaire).
"""
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.core.config import DB_PATH
from app.core.database import init_db
from app.api.routes import router as api_router


# ---------------------------------------------------------------------------
# Application Lifespan Events (Gestionnaire du cycle de vie de l'application)
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Startup and shutdown tasks (Tâches exécutées au démarrage et à l'arrêt).
    Ensures SQLite tables and indexes exist on startup (Initialise les tables et index SQLite au lancement).
    """
    init_db(DB_PATH)
    yield


# ---------------------------------------------------------------------------
# FastAPI Application Factory (Instanciation de l'application FastAPI)
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Smart CRM — La Nouvelle École",
    description="Intelligent lead prioritisation prototype for sales reps (Prototype de priorisation intelligente des prospects)",
    version="1.0.0",
    lifespan=lifespan,
)

# Register modular API router (Enregistrement du routeur API modulaire)
app.include_router(api_router)


# ---------------------------------------------------------------------------
# Static Assets & Frontend Delivery (Distribution des fichiers statiques et de l'interface)
# ---------------------------------------------------------------------------

STATIC_DIR = os.path.join(os.path.dirname(__file__), "..", "static")

# Mount static directory for CSS and JS assets (Montage des ressources statiques CSS et JS)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    """
    Serve the main single page application UI (Fournir l'interface utilisateur web principale).
    """
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))

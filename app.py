import os

from nicegui import ui
from fastapi import FastAPI

from contextlib import asynccontextmanager

from backend.models import init_db
from backend.routers.team import router as teams_router
from backend.routers.player import router as players_router
from backend.routers.match import router as matches_router
from backend.routers.action import router as events_router
from backend.routers.playtime import router as playtime_router
from backend.routers.auth import router as auth_router

# Import pages
from frontend.pages.teams import teams_page
from frontend.pages.matches import matches_page
from frontend.pages.live import live_page
from frontend.pages.analysis import analysis_page
from frontend.pages.login import login_page


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Runs before the app starts serving
    await init_db()#

    yield
    # Runs on shutdown (if needed)

# ------------------------------------------------------------
# BACKEND: FastAPI instance
# ------------------------------------------------------------
app = FastAPI(title="Korfball Stats API",
                      description="Backend API for Korfball Statistics application",
                      version="1.0.0",
                      openapi_url="/api/v1/openapi.json",
                      docs_url="/api/v1/docs",
                      redoc_url="/api/v1/redoc",
                      lifespan=lifespan)

# Mount routers
app.include_router(teams_router, prefix="/api/v1")
app.include_router(players_router, prefix="/api/v1")
app.include_router(matches_router, prefix="/api/v1")
app.include_router(events_router, prefix="/api/v1")
app.include_router(playtime_router, prefix="/api/v1")
app.include_router(auth_router, prefix="/api/v1")

# ------------------------------------------------------------
# Register NiceGUI pages
# ------------------------------------------------------------
@ui.page('/')
def index():
    ui.navigate.to('/teams')

# Mount the NiceGUI app onto the FastAPI app
storage_secret = os.getenv("KORFBALL_STORAGE_SECRET", "dev-storage-secret-change-me")
ui.run_with(
    app=app,
    mount_path='/',
    title="Ganda Korfball Statistics",
    storage_secret=storage_secret,
)


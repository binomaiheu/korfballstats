from nicegui import ui
from fastapi import FastAPI
from backend.db import init_db
from backend.routers.team import router as teams_router
from backend.routers.player import router as players_router
from backend.routers.match import router as matches_router
from backend.routers.event import router as events_router

# Import pages
from frontend.pages.teams import teams_page
from frontend.pages.matches import matches_page
from frontend.pages.events import events_page



# ------------------------------------------------------------
# BACKEND: FastAPI instance
# ------------------------------------------------------------
fastapi_app = FastAPI(title="Korfball Stats API",
                      description="Backend API for Korfball Statistics application",
                      version="1.0.0",
                      openapi_url="/api/v1/openapi.json",
                      docs_url="/api/v1/docs",
                      redoc_url="/api/v1/redoc")

# Mount routers
fastapi_app.include_router(teams_router, prefix="/api/v1")
fastapi_app.include_router(players_router, prefix="/api/v1")
fastapi_app.include_router(matches_router, prefix="/api/v1")
fastapi_app.include_router(events_router, prefix="/api/v1")

ui.run_with(app=fastapi_app, mount_path='/', title="Korfball Stats")


# ------------------------------------------------------------
# Create DB tables once at startup
# ------------------------------------------------------------
@fastapi_app.on_event("startup")
def on_startup():
    init_db()


# ------------------------------------------------------------
# Register NiceGUI pages
# ------------------------------------------------------------

@ui.page("/")
def index():
    ui.label("Korfball Statistics").classes("text-3xl font-bold")
    ui.link("Teams", "/teams")
    ui.link("Matches", "/matches")
    ui.link("Events", "/events")


@ui.page("/teams")
def teams_ui():
    teams_page()


@ui.page("/matches")
def matches_ui():
    matches_page()


@ui.page("/events")
def events_ui():
    events_page()

# ------------------------------------------------------------
# Start app
# ------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:fastapi_app", host="0.0.0.0", port=8855, reload=True)

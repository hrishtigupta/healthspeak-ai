"""FastAPI application entry point.

Run from the backend/ folder:  uvicorn app.main:app --reload --port 8000
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.routers import admin_users, ai_status, auth, departments, health, intakes, patients, users

settings = get_settings()

app = FastAPI(title=settings.app_name, version=settings.app_version)

# Only the known frontend dev origins may call the API from a browser.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Every route lives under /api so it never collides with frontend paths.
for r in (health.router, auth.router, users.router, admin_users.router, patients.router,
          intakes.router, ai_status.router, departments.router):
    app.include_router(r, prefix="/api")

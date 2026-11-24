"""Health endpoints: is the API up, and can it reach the database?"""

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.database.session import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/health", tags=["health"])


@router.get("")
def api_health() -> dict:
    """The API process is running. Does not touch the database."""
    settings = get_settings()
    return {"status": "ok", "service": settings.app_name, "version": settings.app_version}


@router.get("/db")
def database_health(db: Session = Depends(get_db)) -> dict:
    """Runs SELECT 1 against PostgreSQL. Returns 503 if the database is unreachable."""
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        # Log only the error type: the message can contain host/user details.
        logger.error("Database health check failed: %s", type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database unavailable",
        ) from None
    return {"status": "ok", "database": "connected"}

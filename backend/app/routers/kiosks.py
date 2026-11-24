"""Kiosk registration/heartbeat and system health (D8).

- Kiosk device: POST /api/kiosks/heartbeat with header X-Kiosk-Key (no user login).
- Administrators: register/rename/deactivate kiosks, rotate keys, view health.
"""

import uuid
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Response, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.core.enums import Role
from app.core.permissions import require_roles
from app.database.models import Kiosk, User
from app.database.session import get_db
from app.services import kiosk_service

router = APIRouter(tags=["kiosks"])
admin_only = require_roles(Role.ADMIN)


class KioskOut(BaseModel):
    id: uuid.UUID
    code: str
    name: str
    location: str | None
    is_active: bool
    online: bool
    last_seen_at: datetime | None
    app_version: str | None
    last_report: dict | None


class KioskCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{1,39}$")
    name: str = Field(min_length=2, max_length=120)
    location: str | None = Field(default=None, max_length=200)


class KioskUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=2, max_length=120)
    location: str | None = Field(default=None, max_length=200)
    is_active: bool | None = None


class KioskWithKey(KioskOut):
    key: str  # shown once: put it in the kiosk's start-up URL (?kiosk=KEY)


class Heartbeat(BaseModel):
    model_config = ConfigDict(extra="forbid")

    app_version: str | None = Field(default=None, max_length=40)
    ui_language: Literal["en", "hi", "ur"] | None = None
    microphone: Literal["granted", "denied", "prompt", "unknown"] = "unknown"
    online: bool = True


def _out(k: Kiosk, cls=KioskOut, **extra) -> KioskOut:
    return cls(id=k.id, code=k.code, name=k.name, location=k.location, is_active=k.is_active,
               online=kiosk_service.is_online(k), last_seen_at=k.last_seen_at, app_version=k.app_version,
               last_report=k.last_report, **extra)


@router.post("/kiosks/heartbeat", status_code=status.HTTP_204_NO_CONTENT)
def kiosk_heartbeat(body: Heartbeat, x_kiosk_key: str | None = Header(default=None),
                    db: Session = Depends(get_db)) -> Response:
    if not x_kiosk_key or kiosk_service.heartbeat(
            db, x_kiosk_key, app_version=body.app_version,
            report=body.model_dump(exclude={"app_version"})) is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Unknown or inactive kiosk")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/admin/kiosks", response_model=list[KioskOut], dependencies=[Depends(admin_only)])
def list_kiosks(db: Session = Depends(get_db)):
    return [_out(k) for k in kiosk_service.list_kiosks(db)]


@router.post("/admin/kiosks", response_model=KioskWithKey, status_code=status.HTTP_201_CREATED)
def register_kiosk(body: KioskCreate, admin: User = Depends(admin_only), db: Session = Depends(get_db)):
    try:
        k, key = kiosk_service.register(db, code=body.code, name=body.name, location=body.location, actor=admin)
    except kiosk_service.DuplicateCode:
        raise HTTPException(status.HTTP_409_CONFLICT, "A kiosk with this code already exists") from None
    return _out(k, KioskWithKey, key=key)


def _kiosk(kiosk_id: uuid.UUID, db: Session) -> Kiosk:
    k = db.get(Kiosk, kiosk_id)
    if k is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Kiosk not found")
    return k


@router.patch("/admin/kiosks/{kiosk_id}", response_model=KioskOut)
def update_kiosk(kiosk_id: uuid.UUID, body: KioskUpdate, admin: User = Depends(admin_only),
                 db: Session = Depends(get_db)):
    return _out(kiosk_service.update(db, _kiosk(kiosk_id, db), body.model_dump(exclude_unset=True,
                                                                                  exclude_none=True), admin))


@router.post("/admin/kiosks/{kiosk_id}/rotate-key", response_model=KioskWithKey)
def rotate_key(kiosk_id: uuid.UUID, admin: User = Depends(admin_only), db: Session = Depends(get_db)):
    k = _kiosk(kiosk_id, db)
    key = kiosk_service.rotate_key(db, k, admin)
    return _out(k, KioskWithKey, key=key)


@router.get("/admin/system-health", dependencies=[Depends(admin_only)])
def system_health(db: Session = Depends(get_db)) -> dict:
    return kiosk_service.system_health(db)

"""Administrator-only user management."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.enums import Role
from app.core.permissions import require_roles
from app.database.models import User
from app.database.session import get_db
from app.schemas.user import AdminUserCreate, UserList, UserOut
from app.services import user_service

router = APIRouter(prefix="/admin/users", tags=["admin"])

admin_only = require_roles(Role.ADMIN)


@router.get("", response_model=UserList)
def list_users(
    role: Role | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    _: User = Depends(admin_only),
    db: Session = Depends(get_db),
) -> UserList:
    users, total = user_service.list_users(db, limit=limit, offset=offset, role=role)
    return UserList(items=[UserOut.model_validate(u) for u in users], total=total)


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(
    body: AdminUserCreate,
    admin: User = Depends(admin_only),
    db: Session = Depends(get_db),
) -> User:
    try:
        return user_service.create_user(
            db,
            full_name=body.full_name,
            password=body.password,
            role=body.role,
            email=body.email,
            phone=body.phone,
            ui_language=body.ui_language,
            actor_user_id=admin.id,
        )
    except user_service.DuplicateAccountError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email or phone already exists",
        ) from None

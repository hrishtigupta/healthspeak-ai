"""The logged-in user's own profile and preferences."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.permissions import get_current_user
from app.database.models import User
from app.database.session import get_db
from app.schemas.user import PreferencesUpdate, UserOut
from app.services import user_service

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserOut)
def read_me(user: User = Depends(get_current_user)) -> User:
    return user


@router.patch("/me/preferences", response_model=UserOut)
def update_my_preferences(
    body: PreferencesUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> User:
    # Only ever changes THIS user's row: one person's language never affects another's.
    return user_service.set_ui_language(db, user, body.ui_language)

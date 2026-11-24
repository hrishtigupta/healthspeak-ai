"""POST /api/auth/login and POST /api/auth/logout."""

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.core.permissions import get_current_session
from app.database.models import AuthSession
from app.database.session import get_db
from app.schemas.auth import LoginRequest, LoginResponse
from app.schemas.user import UserOut
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)) -> LoginResponse:
    user = auth_service.authenticate(db, body.identifier, body.password)
    if user is None:
        # Same answer for unknown account, wrong password, locked or inactive.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token, session = auth_service.start_session(db, user)
    return LoginResponse(
        access_token=token, expires_at=session.expires_at, user=UserOut.model_validate(user)
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    session: AuthSession = Depends(get_current_session), db: Session = Depends(get_db)
) -> Response:
    auth_service.end_session(db, session)
    return Response(status_code=status.HTTP_204_NO_CONTENT)

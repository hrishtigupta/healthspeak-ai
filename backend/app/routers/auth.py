"""POST /api/auth/login and POST /api/auth/logout."""

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.core.permissions import get_current_session
from app.database.models import AuthSession
from app.database.session import get_db
from app.schemas.auth import LoginRequest, LoginResponse, PasswordResetConfirm, PasswordResetRequest
from app.schemas.user import UserOut
from app.services import auth_service, password_reset_service

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


@router.post("/password-reset/request", status_code=status.HTTP_202_ACCEPTED)
def password_reset_request(body: PasswordResetRequest, db: Session = Depends(get_db)) -> dict:
    """Always the same answer, whether or not a code was sent (no account probing)."""
    password_reset_service.request_code(db, body.identifier)
    return {"detail": "If this account can use online reset, a code has been sent to its mobile number."}


@router.post("/password-reset/confirm", status_code=status.HTTP_204_NO_CONTENT)
def password_reset_confirm(body: PasswordResetConfirm, db: Session = Depends(get_db)) -> Response:
    try:
        password_reset_service.confirm(db, body.identifier, body.code, body.new_password)
    except password_reset_service.InvalidCode:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "The code is wrong or has expired.") from None
    return Response(status_code=status.HTTP_204_NO_CONTENT)

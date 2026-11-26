"""POST /api/auth/login and POST /api/auth/logout."""

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.core.permissions import get_current_session
from app.database.models import AuthSession
from app.database.session import get_db
from app.schemas.auth import LoginRequest, LoginResponse, PasswordResetConfirm, PasswordResetRequest
from app.schemas.user import UserOut
from app.services import auth_service, password_reset_service, sms_service

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
    """Send a code. If SMS cannot be delivered at all, say so (503) instead of pretending."""
    st = sms_service.status()
    if not st.ready:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE,
                            "SMS delivery is not available on this server, so a code cannot be sent. "
                            "Please ask the hospital front desk to reset your password.")
    try:
        issued = password_reset_service.request_code(db, body.identifier)
    except password_reset_service.SendFailed:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE,
                            "We could not send the SMS right now. Please try again in a few minutes, "
                            "or ask the hospital front desk to reset your password.") from None
    out: dict = {"detail": "If this account can use online reset, a code has been sent to its mobile number."}
    if issued is not None and issued.code_for_dev_echo:
        # Development only (APP_ENV=development with the console SMS provider). Never in production.
        out["dev_code"] = issued.code_for_dev_echo
        out["dev_notice"] = "Development mode: no real SMS was sent. This code is shown only because the server is in development mode."
    return out


@router.post("/password-reset/confirm", status_code=status.HTTP_204_NO_CONTENT)
def password_reset_confirm(body: PasswordResetConfirm, db: Session = Depends(get_db)) -> Response:
    try:
        password_reset_service.confirm(db, body.identifier, body.code, body.new_password)
    except password_reset_service.InvalidCode:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "The code is wrong or has expired.") from None
    return Response(status_code=status.HTTP_204_NO_CONTENT)

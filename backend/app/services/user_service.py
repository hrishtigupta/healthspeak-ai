"""Creating, finding and updating user accounts."""

import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.enums import Role, UiLanguage
from app.core.security import hash_password, normalize_email, normalize_phone
from app.database.models import User
from app.services import audit_service


class DuplicateAccountError(Exception):
    """Email or phone already belongs to another account."""


def find_by_identifier(db: Session, identifier: str) -> User | None:
    """Look up an account by email (contains '@') or phone number."""
    identifier = identifier.strip()
    if "@" in identifier:
        return db.scalar(select(User).where(User.email == normalize_email(identifier)))
    phone = normalize_phone(identifier, get_settings().default_phone_country_code)
    if phone is None:
        return None
    return db.scalar(select(User).where(User.phone == phone))


def contact_in_use(db: Session, email: str | None, phone: str | None) -> bool:
    conds = []
    if email:
        conds.append(User.email == email)
    if phone:
        conds.append(User.phone == phone)
    return bool(conds) and db.scalar(select(func.count()).where(or_(*conds))) > 0


def create_user(
    db: Session,
    *,
    full_name: str,
    password: str,
    role: Role,
    email: str | None = None,
    phone: str | None = None,
    ui_language: UiLanguage = UiLanguage.EN,
    actor_user_id: uuid.UUID | None = None,
    commit: bool = True,
) -> User:
    """Create an account. Email/phone are normalised here so every caller is safe."""
    email = normalize_email(email) if email else None
    if phone:
        normalized = normalize_phone(phone, get_settings().default_phone_country_code)
        if normalized is None:
            raise ValueError("Invalid phone number")
        phone = normalized
    else:
        phone = None
    if not email and not phone:
        raise ValueError("Email or phone is required")
    if contact_in_use(db, email, phone):
        raise DuplicateAccountError
    user = User(
        full_name=full_name,
        email=email,
        phone=phone,
        password_hash=hash_password(password),
        role=Role(role).value,
        ui_language=UiLanguage(ui_language).value,
    )
    db.add(user)
    try:
        db.flush()  # assigns user.id and surfaces unique-constraint races
    except IntegrityError:
        db.rollback()
        raise DuplicateAccountError from None
    audit_service.record(
        db, "user.created", actor_user_id=actor_user_id, target_type="user",
        target_id=user.id, details={"role": user.role},
    )
    if commit:
        db.commit()
    return user


def set_ui_language(db: Session, user: User, language: UiLanguage) -> User:
    old = user.ui_language
    user.ui_language = UiLanguage(language).value
    audit_service.record(
        db, "preferences.updated", actor_user_id=user.id, target_type="user", target_id=user.id,
        details={"ui_language": {"from": old, "to": user.ui_language}},
    )
    db.commit()
    db.refresh(user)
    return user


def list_users(db: Session, *, limit: int, offset: int, role: Role | None = None) -> tuple[list[User], int]:
    q = select(User)
    count_q = select(func.count()).select_from(User)
    if role:
        q = q.where(User.role == role.value)
        count_q = count_q.where(User.role == role.value)
    users = list(db.scalars(q.order_by(User.created_at, User.id).limit(limit).offset(offset)))
    return users, db.scalar(count_q) or 0

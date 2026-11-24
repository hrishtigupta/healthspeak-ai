"""D7 Departments and Knowledge Base: departments and routing rules."""

import uuid

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Integer, String, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.database.models.mixins import Timestamps, UuidPk


class Department(UuidPk, Timestamps, Base):
    __tablename__ = "departments"

    code: Mapped[str] = mapped_column(String(40), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str | None] = mapped_column(String(500))
    # The fallback suggestion when no routing rule matches (exactly one should be set).
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))


class RoutingRule(UuidPk, Timestamps, Base):
    __tablename__ = "routing_rules"
    __table_args__ = (
        CheckConstraint("kind IN ('route', 'attention')", name="kind_valid"),
        CheckConstraint("weight BETWEEN 1 AND 10", name="weight_range"),
        CheckConstraint("kind = 'attention' OR department_id IS NOT NULL", name="route_has_department"),
    )

    kind: Mapped[str] = mapped_column(String(16))
    phrase: Mapped[str] = mapped_column(String(100))
    weight: Mapped[int] = mapped_column(Integer, default=1)
    department_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("departments.id", ondelete="RESTRICT"), index=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL")
    )

    department: Mapped[Department | None] = relationship(lazy="joined")

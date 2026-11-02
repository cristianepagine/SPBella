import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, String, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import TenantBase

ROLES = ("owner", "reception", "professional")


class User(TenantBase):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("role IN ('owner', 'reception', 'professional')", name="role"),
        CheckConstraint("email = lower(email)", name="email_lowercase"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(254), unique=True)
    password_hash: Mapped[str] = mapped_column(Text)
    role: Mapped[str] = mapped_column(String(16))
    must_change_password: Mapped[bool] = mapped_column(server_default=text("false"))
    is_active: Mapped[bool] = mapped_column(server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

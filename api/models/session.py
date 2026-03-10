from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, LargeBinary, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class Session(Base):
    __tablename__ = "sessions"
    __table_args__ = (
        UniqueConstraint("account_id", "origin_domain", name="sessions_account_id_origin_domain_key"),
        CheckConstraint(
            "auth_state IN ('active', 'stale', 'expired')",
            name="sessions_auth_state_check",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, server_default=text("uuid_generate_v7()")
    )
    account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("accounts.id"), nullable=False)
    origin_domain: Mapped[str] = mapped_column(String, nullable=False)
    cookies_encrypted: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    auth_state: Mapped[str | None] = mapped_column(String)
    last_used_at: Mapped[datetime | None] = mapped_column(server_default=text("now()"))
    expires_at: Mapped[datetime | None] = mapped_column()
    created_at: Mapped[datetime | None] = mapped_column(server_default=text("now()"))

    account: Mapped[Account] = relationship(back_populates="sessions")


from .account import Account  # noqa: E402

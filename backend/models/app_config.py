from datetime import datetime

from sqlalchemy import DateTime, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from backend.database import Base


class AppConfig(Base):
    """Key/value store for runtime config OVERRIDES over the env-baked Settings.

    Only whitelisted keys are ever written here (see backend/services/runtime_config.py).
    A missing row means "use the env default", so behaviour is identical to today until
    an admin flips something. Value is JSONB so a key can hold a string, bool, etc.
    """

    __tablename__ = "app_config"

    key: Mapped[str] = mapped_column(Text, primary_key=True)
    value: Mapped[object] = mapped_column(JSONB, nullable=False)
    updated_by: Mapped[str | None] = mapped_column(Text)  # admin email, for the audit trail
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

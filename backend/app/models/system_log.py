"""SQLAlchemy ORM for system_logs — observability + pause flag."""
from __future__ import annotations

from typing import Any

from sqlalchemy import JSON, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class SystemLogORM(Base, TimestampMixin):
    __tablename__ = "system_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    level: Mapped[str] = mapped_column(String(16), nullable=False)
    source: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    context: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    trace_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)

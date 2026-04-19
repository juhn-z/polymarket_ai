"""SQLAlchemy ORM model for the markets table."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class MarketORM(Base, TimestampMixin):
    __tablename__ = "markets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    polymarket_condition_id: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    polymarket_token_id: Mapped[str] = mapped_column(String(128), nullable=False)
    event_slug: Mapped[str] = mapped_column(String(255), nullable=False)
    question: Mapped[str] = mapped_column(String(500), nullable=False)
    price_threshold: Mapped[int] = mapped_column(Integer, nullable=False)
    scan_date: Mapped[date] = mapped_column(Date, nullable=False, unique=True, index=True)
    target_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    current_yes_price: Mapped[Decimal] = mapped_column(Numeric(38, 18), nullable=False)
    current_no_price: Mapped[Decimal] = mapped_column(Numeric(38, 18), nullable=False)
    selected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")
    resolution: Mapped[str | None] = mapped_column(String(8), nullable=True)

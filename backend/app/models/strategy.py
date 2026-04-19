"""SQLAlchemy ORM for the strategies table."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class StrategyORM(Base, TimestampMixin):
    __tablename__ = "strategies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    prediction_id: Mapped[int] = mapped_column(
        ForeignKey("predictions.id"), nullable=False, index=True
    )
    market_id: Mapped[int] = mapped_column(
        ForeignKey("markets.id"), nullable=False, index=True
    )

    action: Mapped[str] = mapped_column(String(16), nullable=False)
    side: Mapped[str | None] = mapped_column(String(8), nullable=True)
    position_size: Mapped[Decimal] = mapped_column(Numeric(38, 18), nullable=False)
    entry_price: Mapped[Decimal] = mapped_column(Numeric(38, 18), nullable=False)
    take_profit: Mapped[Decimal] = mapped_column(Numeric(38, 18), nullable=False)
    stop_loss: Mapped[Decimal] = mapped_column(Numeric(38, 18), nullable=False)
    kelly_fraction: Mapped[Decimal] = mapped_column(Numeric(38, 18), nullable=False)
    edge: Mapped[Decimal] = mapped_column(Numeric(38, 18), nullable=False)
    skip_reason: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    executed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

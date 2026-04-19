"""SQLAlchemy ORM for the vault_snapshots table."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Integer, Numeric
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class VaultSnapshotORM(Base, TimestampMixin):
    __tablename__ = "vault_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    total_assets: Mapped[Decimal] = mapped_column(Numeric(38, 18), nullable=False)
    share_price: Mapped[Decimal] = mapped_column(Numeric(38, 18), nullable=False)
    tvl: Mapped[Decimal] = mapped_column(Numeric(38, 18), nullable=False)
    depositor_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    deployed_amount: Mapped[Decimal] = mapped_column(Numeric(38, 18), nullable=False, default=Decimal("0"))
    snapshot_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)

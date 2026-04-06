from datetime import datetime
from decimal import Decimal
from typing import Optional, Dict, Any
import uuid

from sqlalchemy import String, Numeric, DateTime, func, Index, JSON, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.core.enums import PaymentStatus, Currency


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True, name="metadata")
    status: Mapped[str] = mapped_column(String(20), default=PaymentStatus.PENDING.value)
    idempotency_key: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    webhook_url: Mapped[Optional[str]] = mapped_column(String(2048), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    processed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("idx_payment_status", "status"),
        Index("idx_payment_created_at", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<Payment(id={self.id}, status={self.status}, amount={self.amount} {self.currency})>"


class OutboxEvent(Base):
    __tablename__ = "outbox_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    payload: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending, published, failed
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    max_retries: Mapped[int] = mapped_column(Integer, default=3)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("idx_outbox_status", "status"),
        Index("idx_outbox_created_at", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<OutboxEvent(id={self.id}, type={self.event_type}, status={self.status})>"

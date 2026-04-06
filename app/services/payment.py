from datetime import datetime
from decimal import Decimal
from typing import Optional, Dict, Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models.payment import Payment, OutboxEvent
from app.core.enums import PaymentStatus


class PaymentService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_payment(
        self,
        amount: Decimal,
        currency: str,
        description: str,
        idempotency_key: str,
        metadata: Optional[Dict[str, Any]] = None,
        webhook_url: Optional[str] = None,
    ) -> Payment:
        """Create a new payment with idempotency check."""
        # Check for existing payment with same idempotency key
        existing = await self.get_payment_by_idempotency_key(idempotency_key)
        if existing:
            return existing

        payment = Payment(
            amount=amount,
            currency=currency,
            description=description,
            idempotency_key=idempotency_key,
            metadata_=metadata,
            webhook_url=webhook_url,
            status=PaymentStatus.PENDING.value,
        )

        self.session.add(payment)
        await self.session.flush()

        # Create outbox event for guaranteed delivery
        outbox_event = OutboxEvent(
            event_type="payment.created",
            payload={
                "payment_id": payment.id,
                "amount": str(amount),
                "currency": currency,
                "description": description,
                "idempotency_key": idempotency_key,
                "webhook_url": webhook_url,
            },
            status="pending",
        )
        self.session.add(outbox_event)

        return payment

    async def get_payment(self, payment_id: str) -> Optional[Payment]:
        """Get payment by ID."""
        result = await self.session.execute(select(Payment).where(Payment.id == payment_id))
        return result.scalar_one_or_none()

    async def get_payment_by_idempotency_key(self, idempotency_key: str) -> Optional[Payment]:
        """Get payment by idempotency key."""
        result = await self.session.execute(
            select(Payment).where(Payment.idempotency_key == idempotency_key)
        )
        return result.scalar_one_or_none()

    async def update_payment_status(
        self,
        payment_id: str,
        status: PaymentStatus,
        processed_at: Optional[datetime] = None,
    ) -> Optional[Payment]:
        """Update payment status."""
        payment = await self.get_payment(payment_id)
        if not payment:
            return None

        payment.status = status.value
        payment.processed_at = processed_at or datetime.utcnow()

        await self.session.flush()
        return payment

    async def get_pending_outbox_events(self, limit: int = 100) -> list[OutboxEvent]:
        """Get pending outbox events for publishing."""
        result = await self.session.execute(
            select(OutboxEvent)
            .where(OutboxEvent.status == "pending")
            .order_by(OutboxEvent.created_at)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def mark_outbox_published(self, event_id: int) -> None:
        """Mark outbox event as published."""
        event = await self.session.get(OutboxEvent, event_id)
        if event:
            event.status = "published"
            event.published_at = datetime.utcnow()
            await self.session.flush()

    async def mark_outbox_failed(self, event_id: int, error_message: str) -> None:
        """Mark outbox event as failed."""
        event = await self.session.get(OutboxEvent, event_id)
        if event:
            event.retry_count += 1
            if event.retry_count >= event.max_retries:
                event.status = "failed"
            else:
                event.status = "pending"
            event.error_message = error_message
            await self.session.flush()

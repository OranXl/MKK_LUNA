"""Tests for payment service."""
import pytest
from decimal import Decimal
from datetime import datetime

from sqlalchemy import select

from app.services.payment import PaymentService
from app.models.payment import Payment, OutboxEvent
from app.core.enums import PaymentStatus


class TestPaymentService:
    """Tests for PaymentService class."""

    @pytest.mark.asyncio
    async def test_create_payment(self, db_session, sample_payment_data, sample_idempotency_key):
        """Test creating a new payment."""
        service = PaymentService(db_session)
        
        payment = await service.create_payment(
            amount=Decimal(sample_payment_data["amount"]),
            currency=sample_payment_data["currency"],
            description=sample_payment_data["description"],
            idempotency_key=sample_idempotency_key,
            metadata=sample_payment_data["metadata"],
            webhook_url=sample_payment_data["webhook_url"],
        )
        
        assert payment is not None
        assert payment.amount == Decimal("1000.00")
        assert payment.currency == "RUB"
        assert payment.description == "Test payment description"
        assert payment.status == PaymentStatus.PENDING.value
        assert payment.idempotency_key == sample_idempotency_key
        assert payment.metadata_ == {"order_id": "12345", "user_id": "67890"}
        
        # Verify outbox event was created
        result = await db_session.execute(select(OutboxEvent))
        events = result.scalars().all()
        assert len(events) == 1
        assert events[0].event_type == "payment.created"
        assert events[0].payload["payment_id"] == payment.id

    @pytest.mark.asyncio
    async def test_create_payment_idempotency(self, db_session, sample_payment_data, sample_idempotency_key):
        """Test that creating payment with same idempotency key returns existing payment."""
        service = PaymentService(db_session)
        
        # Create first payment
        payment1 = await service.create_payment(
            amount=Decimal(sample_payment_data["amount"]),
            currency=sample_payment_data["currency"],
            description=sample_payment_data["description"],
            idempotency_key=sample_idempotency_key,
        )
        
        # Try to create another payment with same idempotency key
        payment2 = await service.create_payment(
            amount=Decimal("2000.00"),  # Different amount
            currency="USD",  # Different currency
            description="Different description",
            idempotency_key=sample_idempotency_key,
        )
        
        # Should return the same payment
        assert payment1.id == payment2.id
        assert payment2.amount == Decimal("1000.00")  # Original amount
        
        # Only one outbox event should be created
        result = await db_session.execute(select(OutboxEvent))
        events = result.scalars().all()
        assert len(events) == 1

    @pytest.mark.asyncio
    async def test_get_payment(self, db_session, sample_payment_data, sample_idempotency_key):
        """Test getting a payment by ID."""
        service = PaymentService(db_session)
        
        # Create a payment
        payment = await service.create_payment(
            amount=Decimal(sample_payment_data["amount"]),
            currency=sample_payment_data["currency"],
            description=sample_payment_data["description"],
            idempotency_key=sample_idempotency_key,
        )
        
        # Get the payment
        retrieved = await service.get_payment(payment.id)
        
        assert retrieved is not None
        assert retrieved.id == payment.id
        assert retrieved.amount == payment.amount

    @pytest.mark.asyncio
    async def test_get_payment_not_found(self, db_session):
        """Test getting a non-existent payment."""
        service = PaymentService(db_session)
        
        payment = await service.get_payment("non-existent-id")
        assert payment is None

    @pytest.mark.asyncio
    async def test_get_payment_by_idempotency_key(self, db_session, sample_payment_data, sample_idempotency_key):
        """Test getting a payment by idempotency key."""
        service = PaymentService(db_session)
        
        # Create a payment
        payment = await service.create_payment(
            amount=Decimal(sample_payment_data["amount"]),
            currency=sample_payment_data["currency"],
            description=sample_payment_data["description"],
            idempotency_key=sample_idempotency_key,
        )
        
        # Get by idempotency key
        retrieved = await service.get_payment_by_idempotency_key(sample_idempotency_key)
        
        assert retrieved is not None
        assert retrieved.id == payment.id

    @pytest.mark.asyncio
    async def test_update_payment_status(self, db_session, sample_payment_data, sample_idempotency_key):
        """Test updating payment status."""
        service = PaymentService(db_session)
        
        # Create a payment
        payment = await service.create_payment(
            amount=Decimal(sample_payment_data["amount"]),
            currency=sample_payment_data["currency"],
            description=sample_payment_data["description"],
            idempotency_key=sample_idempotency_key,
        )
        
        assert payment.status == PaymentStatus.PENDING.value
        
        # Update status
        updated = await service.update_payment_status(
            payment_id=payment.id,
            status=PaymentStatus.SUCCEEDED,
        )
        
        assert updated is not None
        assert updated.status == PaymentStatus.SUCCEEDED.value
        assert updated.processed_at is not None

    @pytest.mark.asyncio
    async def test_update_payment_status_not_found(self, db_session):
        """Test updating status of non-existent payment."""
        service = PaymentService(db_session)
        
        updated = await service.update_payment_status(
            payment_id="non-existent-id",
            status=PaymentStatus.SUCCEEDED,
        )
        
        assert updated is None

    @pytest.mark.asyncio
    async def test_get_pending_outbox_events(self, db_session, sample_payment_data, sample_idempotency_key):
        """Test getting pending outbox events."""
        service = PaymentService(db_session)
        
        # Create multiple payments
        for i in range(3):
            await service.create_payment(
                amount=Decimal(sample_payment_data["amount"]),
                currency=sample_payment_data["currency"],
                description=f"Payment {i}",
                idempotency_key=f"{sample_idempotency_key}-{i}",
            )
        
        # Get pending events
        events = await service.get_pending_outbox_events()
        
        assert len(events) == 3
        for event in events:
            assert event.status == "pending"
            assert event.event_type == "payment.created"

    @pytest.mark.asyncio
    async def test_mark_outbox_published(self, db_session, sample_payment_data, sample_idempotency_key):
        """Test marking outbox event as published."""
        service = PaymentService(db_session)
        
        # Create a payment
        await service.create_payment(
            amount=Decimal(sample_payment_data["amount"]),
            currency=sample_payment_data["currency"],
            description=sample_payment_data["description"],
            idempotency_key=sample_idempotency_key,
        )
        
        # Get the event
        events = await service.get_pending_outbox_events()
        event_id = events[0].id
        
        # Mark as published
        await service.mark_outbox_published(event_id)
        
        # Verify
        result = await db_session.execute(select(OutboxEvent).where(OutboxEvent.id == event_id))
        event = result.scalar_one_or_none()
        
        assert event is not None
        assert event.status == "published"
        assert event.published_at is not None

    @pytest.mark.asyncio
    async def test_mark_outbox_failed(self, db_session, sample_payment_data, sample_idempotency_key):
        """Test marking outbox event as failed after retries."""
        service = PaymentService(db_session)
        
        # Create a payment
        await service.create_payment(
            amount=Decimal(sample_payment_data["amount"]),
            currency=sample_payment_data["currency"],
            description=sample_payment_data["description"],
            idempotency_key=sample_idempotency_key,
        )
        
        # Get the event
        events = await service.get_pending_outbox_events()
        event_id = events[0].id
        
        # Mark as failed multiple times (should reach max_retries)
        for i in range(4):
            await service.mark_outbox_failed(event_id, f"Error {i}")
        
        # Verify
        result = await db_session.execute(select(OutboxEvent).where(OutboxEvent.id == event_id))
        event = result.scalar_one_or_none()
        
        assert event is not None
        assert event.status == "failed"
        assert event.retry_count >= event.max_retries
        assert event.error_message == "Error 3"

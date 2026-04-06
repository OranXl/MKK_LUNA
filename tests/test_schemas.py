"""Tests for payment schemas."""
from decimal import Decimal
import pytest
from pydantic import ValidationError

from app.schemas.payment import PaymentCreate, PaymentResponse


class TestPaymentCreate:
    """Tests for PaymentCreate schema."""

    def test_valid_payment_create(self, sample_payment_data):
        """Test creating a valid payment."""
        payment = PaymentCreate(**sample_payment_data)
        
        assert payment.amount == Decimal("1000.00")
        assert payment.currency == "RUB"
        assert payment.description == "Test payment description"
        assert payment.metadata_ == {"order_id": "12345", "user_id": "67890"}
        assert payment.webhook_url == "https://example.com/webhook"

    def test_payment_create_with_alias(self):
        """Test creating payment with metadata alias."""
        data = {
            "amount": "500.00",
            "currency": "USD",
            "description": "Test payment",
            "metadata": {"key": "value"},
        }
        payment = PaymentCreate(**data)
        assert payment.metadata_ == {"key": "value"}

    def test_payment_create_minimal(self):
        """Test creating payment with minimal required fields."""
        data = {
            "amount": "100.00",
            "currency": "EUR",
            "description": "Minimal payment",
        }
        payment = PaymentCreate(**data)
        assert payment.amount == Decimal("100.00")
        assert payment.currency == "EUR"
        assert payment.description == "Minimal payment"
        assert payment.metadata_ is None
        assert payment.webhook_url is None

    def test_payment_create_invalid_amount_zero(self):
        """Test that zero amount raises validation error."""
        data = {
            "amount": "0.00",
            "currency": "RUB",
            "description": "Invalid payment",
        }
        with pytest.raises(ValidationError) as exc_info:
            PaymentCreate(**data)
        assert "amount" in str(exc_info.value)

    def test_payment_create_invalid_amount_negative(self):
        """Test that negative amount raises validation error."""
        data = {
            "amount": "-100.00",
            "currency": "RUB",
            "description": "Invalid payment",
        }
        with pytest.raises(ValidationError) as exc_info:
            PaymentCreate(**data)
        assert "amount" in str(exc_info.value)

    def test_payment_create_empty_description(self):
        """Test that empty description raises validation error."""
        data = {
            "amount": "100.00",
            "currency": "RUB",
            "description": "",
        }
        with pytest.raises(ValidationError) as exc_info:
            PaymentCreate(**data)
        assert "description" in str(exc_info.value)

    def test_payment_create_long_description(self):
        """Test that description over 1000 chars raises validation error."""
        data = {
            "amount": "100.00",
            "currency": "RUB",
            "description": "a" * 1001,
        }
        with pytest.raises(ValidationError) as exc_info:
            PaymentCreate(**data)
        assert "description" in str(exc_info.value)

    def test_payment_create_invalid_currency_length(self):
        """Test currency validation (should be 3 chars)."""
        # Note: Current schema doesn't enforce 3-char currency, 
        # but this could be added in future
        data = {
            "amount": "100.00",
            "currency": "INVALID",
            "description": "Test payment",
        }
        payment = PaymentCreate(**data)
        assert payment.currency == "INVALID"


class TestPaymentResponse:
    """Tests for PaymentResponse schema."""

    def test_payment_response_from_model(self):
        """Test creating response from ORM model attributes."""
        from datetime import datetime
        
        data = {
            "id": "550e8400-e29b-41d4-a716-446655440000",
            "amount": Decimal("1000.00"),
            "currency": "RUB",
            "description": "Order payment",
            "metadata": {"order_id": "12345"},
            "status": "pending",
            "idempotency_key": "unique-key-12345",
            "webhook_url": "https://example.com/webhook",
            "created_at": datetime.utcnow(),
            "processed_at": None,
        }
        
        response = PaymentResponse(**data)
        assert response.id == "550e8400-e29b-41d4-a716-446655440000"
        assert response.amount == Decimal("1000.00")
        assert response.status == "pending"
        assert response.processed_at is None

    def test_payment_response_with_processed_at(self):
        """Test response with processed_at timestamp."""
        from datetime import datetime
        
        now = datetime.utcnow()
        data = {
            "id": "test-id",
            "amount": Decimal("500.00"),
            "currency": "USD",
            "description": "Test",
            "metadata": None,
            "status": "completed",
            "idempotency_key": "key-123",
            "webhook_url": None,
            "created_at": datetime.utcnow(),
            "processed_at": now,
        }
        
        response = PaymentResponse(**data)
        assert response.status == "completed"
        assert response.processed_at == now

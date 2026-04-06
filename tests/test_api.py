"""Tests for payment API endpoints."""
import pytest
from decimal import Decimal

from app.models.payment import Payment, OutboxEvent
from app.core.enums import PaymentStatus


class TestCreatePayment:
    """Tests for POST /api/v1/payments endpoint."""

    @pytest.mark.asyncio
    async def test_create_payment_success(self, client, sample_payment_data, sample_idempotency_key, sample_api_key):
        """Test successful payment creation."""
        response = await client.post(
            "/api/v1/payments",
            json=sample_payment_data,
            headers={
                "X-API-Key": sample_api_key,
                "Idempotency-Key": sample_idempotency_key,
            },
        )
        
        assert response.status_code == 202
        data = response.json()
        
        assert "id" in data
        assert data["amount"] == "1000.00"
        assert data["currency"] == "RUB"
        assert data["description"] == "Test payment description"
        assert data["status"] == "pending"
        assert data["idempotency_key"] == sample_idempotency_key
        assert data["metadata"]["order_id"] == "12345"

    @pytest.mark.asyncio
    async def test_create_payment_idempotency(self, client, sample_payment_data, sample_idempotency_key, sample_api_key):
        """Test idempotency - same key returns same payment."""
        # First request
        response1 = await client.post(
            "/api/v1/payments",
            json=sample_payment_data,
            headers={
                "X-API-Key": sample_api_key,
                "Idempotency-Key": sample_idempotency_key,
            },
        )
        
        # Second request with different data but same idempotency key
        modified_data = sample_payment_data.copy()
        modified_data["amount"] = "2000.00"
        
        response2 = await client.post(
            "/api/v1/payments",
            json=modified_data,
            headers={
                "X-API-Key": sample_api_key,
                "Idempotency-Key": sample_idempotency_key,
            },
        )
        
        assert response1.status_code == 202
        assert response2.status_code == 202
        
        data1 = response1.json()
        data2 = response2.json()
        
        # Should return the same payment
        assert data1["id"] == data2["id"]
        assert data2["amount"] == "1000.00"  # Original amount

    @pytest.mark.asyncio
    async def test_create_payment_missing_api_key(self, client, sample_payment_data, sample_idempotency_key):
        """Test payment creation without API key."""
        response = await client.post(
            "/api/v1/payments",
            json=sample_payment_data,
            headers={"Idempotency-Key": sample_idempotency_key},
        )
        
        assert response.status_code == 422  # Missing required header

    @pytest.mark.asyncio
    async def test_create_payment_invalid_api_key(self, client, sample_payment_data, sample_idempotency_key):
        """Test payment creation with invalid API key."""
        response = await client.post(
            "/api/v1/payments",
            json=sample_payment_data,
            headers={
                "X-API-Key": "invalid-key",
                "Idempotency-Key": sample_idempotency_key,
            },
        )
        
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_create_payment_missing_idempotency_key(self, client, sample_payment_data, sample_api_key):
        """Test payment creation without idempotency key."""
        response = await client.post(
            "/api/v1/payments",
            json=sample_payment_data,
            headers={"X-API-Key": sample_api_key},
        )
        
        assert response.status_code == 422  # Missing required header

    @pytest.mark.asyncio
    async def test_create_payment_invalid_amount(self, client, sample_idempotency_key, sample_api_key):
        """Test payment creation with invalid amount."""
        data = {
            "amount": "-100.00",
            "currency": "RUB",
            "description": "Invalid payment",
        }
        
        response = await client.post(
            "/api/v1/payments",
            json=data,
            headers={
                "X-API-Key": sample_api_key,
                "Idempotency-Key": sample_idempotency_key,
            },
        )
        
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_payment_empty_description(self, client, sample_idempotency_key, sample_api_key):
        """Test payment creation with empty description."""
        data = {
            "amount": "100.00",
            "currency": "RUB",
            "description": "",
        }
        
        response = await client.post(
            "/api/v1/payments",
            json=data,
            headers={
                "X-API-Key": sample_api_key,
                "Idempotency-Key": sample_idempotency_key,
            },
        )
        
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_payment_uppercase_currency(self, client, sample_payment_data, sample_idempotency_key, sample_api_key):
        """Test that currency is converted to uppercase."""
        data = sample_payment_data.copy()
        data["currency"] = "rub"  # lowercase
        
        response = await client.post(
            "/api/v1/payments",
            json=data,
            headers={
                "X-API-Key": sample_api_key,
                "Idempotency-Key": sample_idempotency_key,
            },
        )
        
        assert response.status_code == 202
        data = response.json()
        assert data["currency"] == "RUB"


class TestGetPayment:
    """Tests for GET /api/v1/payments/{payment_id} endpoint."""

    @pytest.mark.asyncio
    async def test_get_payment_success(self, client, db_session, sample_api_key):
        """Test successful payment retrieval."""
        from app.services.payment import PaymentService
        
        # Create a payment first
        service = PaymentService(db_session)
        payment = await service.create_payment(
            amount=Decimal("1000.00"),
            currency="RUB",
            description="Test payment",
            idempotency_key="test-key-get",
        )
        await db_session.commit()
        
        # Get the payment
        response = await client.get(
            f"/api/v1/payments/{payment.id}",
            headers={"X-API-Key": sample_api_key},
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["id"] == payment.id
        assert data["amount"] == "1000.00"
        assert data["description"] == "Test payment"

    @pytest.mark.asyncio
    async def test_get_payment_not_found(self, client, sample_api_key):
        """Test getting non-existent payment."""
        response = await client.get(
            "/api/v1/payments/non-existent-id",
            headers={"X-API-Key": sample_api_key},
        )
        
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_payment_missing_api_key(self, client, db_session):
        """Test getting payment without API key."""
        from app.services.payment import PaymentService
        
        # Create a payment first
        service = PaymentService(db_session)
        payment = await service.create_payment(
            amount=Decimal("1000.00"),
            currency="RUB",
            description="Test payment",
            idempotency_key="test-key-get-no-auth",
        )
        await db_session.commit()
        
        response = await client.get(f"/api/v1/payments/{payment.id}")
        assert response.status_code == 422

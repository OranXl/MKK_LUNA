from datetime import datetime
from decimal import Decimal
from typing import Optional, Dict, Any

from pydantic import BaseModel, Field, ConfigDict, field_validator


class PaymentCreate(BaseModel):
    amount: Decimal = Field(..., gt=0, description="Payment amount")
    currency: str = Field(..., description="Currency code (RUB, USD, EUR)")
    description: str = Field(..., min_length=1, max_length=1000, description="Payment description")
    metadata_: Optional[Dict[str, Any]] = Field(None, alias="metadata", description="Additional metadata")
    webhook_url: Optional[str] = Field(None, description="Webhook URL for notifications")

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "amount": 1000.00,
                "currency": "RUB",
                "description": "Order payment #12345",
                "metadata": {"order_id": "12345", "user_id": "67890"},
                "webhook_url": "https://example.com/webhook"
            }
        }
    )


class PaymentResponse(BaseModel):
    """Response model for payment creation (202 Accepted)."""
    id: str = Field(..., alias="payment_id", description="Payment ID")
    status: str = Field(..., description="Payment status")
    created_at: datetime = Field(..., description="Payment creation timestamp")
    
    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "payment_id": "550e8400-e29b-41d4-a716-446655440000",
                "status": "pending",
                "created_at": "2024-01-01T12:00:00Z"
            }
        }
    )


class PaymentStatusUpdate(BaseModel):
    payment_id: str
    status: str
    processed_at: datetime

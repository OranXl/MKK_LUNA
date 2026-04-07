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
    id: str
    amount: Decimal
    currency: str
    description: str
    status: str
    idempotency_key: str
    webhook_url: Optional[str]
    created_at: datetime
    processed_at: Optional[datetime]
    metadata: Optional[Dict[str, Any]] = Field(None, alias='_metadata')
    
    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "amount": 1000.00,
                "currency": "RUB",
                "description": "Order payment #12345",
                "metadata": {"order_id": "12345", "user_id": "67890"},
                "status": "pending",
                "idempotency_key": "unique-key-12345",
                "webhook_url": "https://example.com/webhook",
                "created_at": "2024-01-01T12:00:00Z",
                "processed_at": None
            }
        }
    )
    
    @field_validator('metadata', mode='before')
    @classmethod
    def validate_metadata(cls, v):
        """Ensure metadata is a dict or None."""
        from sqlalchemy.sql.schema import MetaData
        if isinstance(v, MetaData) or not isinstance(v, (dict, type(None))):
            return None
        return v


class PaymentStatusUpdate(BaseModel):
    payment_id: str
    status: str
    processed_at: datetime

from fastapi import APIRouter, Depends, HTTPException, status, Header
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.payment import PaymentCreate, PaymentResponse, PaymentDetails
from app.services.payment import PaymentService
from app.core.config import get_settings

settings = get_settings()
router = APIRouter(prefix="/api/v1", tags=["payments"])


async def verify_api_key(x_api_key: str = Header(..., description="API Key")):
    """Verify API key from header."""
    if x_api_key != settings.api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )


@router.post(
    "/payments",
    response_model=PaymentResponse,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(verify_api_key)],
)
async def create_payment(
    payment_data: PaymentCreate,
    idempotency_key: str = Header(..., description="Idempotency key to prevent duplicates"),
    db: AsyncSession = Depends(get_db),
):
    """
    Create a new payment.
    
    - **amount**: Payment amount (must be positive)
    - **currency**: Currency code (RUB, USD, EUR)
    - **description**: Payment description
    - **metadata**: Optional additional metadata
    - **webhook_url**: Optional URL for result notification
    """
    service = PaymentService(db)
    
    try:
        payment = await service.create_payment(
            amount=payment_data.amount,
            currency=payment_data.currency.upper(),
            description=payment_data.description,
            idempotency_key=idempotency_key,
            metadata=payment_data.metadata_,
            webhook_url=payment_data.webhook_url,
        )
        
        return payment
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create payment: {str(e)}",
        )


@router.get(
    "/payments/{payment_id}",
    response_model=PaymentDetails,
    dependencies=[Depends(verify_api_key)],
)
async def get_payment(
    payment_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Get detailed payment information by ID.
    
    Returns full payment details including amount, currency, description, metadata, and processing timestamps.
    """
    service = PaymentService(db)
    payment = await service.get_payment(payment_id)
    
    if not payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment not found",
        )
    
    return payment

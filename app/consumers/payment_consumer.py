import asyncio
import random
from datetime import datetime
from typing import Dict, Any

import aiohttp
from faststream import FastStream
from faststream.rabbit import RabbitBroker, RabbitExchange, RabbitQueue

from app.core.config import get_settings
from app.db.session import async_session_maker, engine, Base
from app.models.payment import Payment, OutboxEvent
from app.core.enums import PaymentStatus
from sqlalchemy import select, update

settings = get_settings()

# Создаем брокер
broker = RabbitBroker(settings.rabbitmq_url)

# Объявляем обменник и очереди
payments_exchange = RabbitExchange("payments", type="direct", durable=True)
payments_queue = RabbitQueue(settings.payments_queue, durable=True)
dlq_queue = RabbitQueue(settings.dlq_queue, durable=True)

app = FastStream(broker)


async def simulate_payment_processing() -> tuple[bool, str]:
    """
    Simulate payment processing.
    Returns (success, message) tuple.
    90% success rate, 10% failure rate.
    Processing time: 2-5 seconds.
    """
    processing_time = random.uniform(2, 5)
    await asyncio.sleep(processing_time)
    
    is_success = random.random() < 0.9
    if is_success:
        return True, "Payment processed successfully"
    else:
        return False, "Payment gateway error: transaction declined"


async def send_webhook(webhook_url: str, payload: Dict[str, Any], max_retries: int = 3) -> bool:
    """
    Send webhook notification with retry logic.
    Uses exponential backoff for retries.
    """
    async with aiohttp.ClientSession() as session:
        for attempt in range(max_retries):
            try:
                async with session.post(
                    webhook_url,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as response:
                    if response.status in (200, 201, 202, 204):
                        return True
                    else:
                        raise Exception(f"Webhook returned status {response.status}")
            except Exception as e:
                if attempt < max_retries - 1:
                    delay = settings.retry_base_delay * (2 ** attempt)
                    await asyncio.sleep(delay)
                else:
                    print(f"Failed to send webhook after {max_retries} attempts: {e}")
                    return False
    return False


@broker.subscriber(
    queue=payments_queue,
    exchange=payments_exchange,
)
async def process_payment(message: Dict[str, Any]):
    """
    Consumer for processing new payments.
    
    1. Receives message from queue
    2. Simulates payment processing (2-5 sec, 90% success)
    3. Updates payment status in DB
    4. Sends webhook notification
    5. Handles retries and DLQ
    """
    payment_id = message.get("payment_id")
    webhook_url = message.get("webhook_url")
    
    async with async_session_maker() as session:
        try:
            # Get payment
            result = await session.execute(select(Payment).where(Payment.id == payment_id))
            payment = result.scalar_one_or_none()
            
            if not payment:
                print(f"Payment {payment_id} not found")
                return
            
            # Simulate payment processing
            success, processing_message = await simulate_payment_processing()
            
            # Update payment status
            if success:
                payment.status = PaymentStatus.SUCCEEDED.value
            else:
                payment.status = PaymentStatus.FAILED.value
            
            payment.processed_at = datetime.utcnow()
            await session.commit()
            
            # Send webhook notification
            if webhook_url:
                webhook_payload = {
                    "payment_id": payment.id,
                    "status": payment.status,
                    "amount": str(payment.amount),
                    "currency": payment.currency,
                    "processed_at": payment.processed_at.isoformat(),
                    "message": processing_message,
                }
                
                webhook_sent = await send_webhook(webhook_url, webhook_payload)
                
                if not webhook_sent:
                    print(f"Failed to send webhook for payment {payment_id}")
                    # Re-queue for retry by raising exception
                    raise Exception("Webhook delivery failed")
            
            print(f"Payment {payment_id} processed successfully: {payment.status}")
            
        except Exception as e:
            await session.rollback()
            print(f"Error processing payment {payment_id}: {e}")
            
            # Update outbox event for retry
            async with async_session_maker() as retry_session:
                result = await retry_session.execute(
                    select(OutboxEvent).where(
                        OutboxEvent.payload["payment_id"].as_string() == payment_id
                    )
                )
                outbox_event = result.scalar_one_or_none()
                
                if outbox_event:
                    outbox_event.retry_count += 1
                    
                    if outbox_event.retry_count >= settings.max_retries:
                        # Move to DLQ
                        outbox_event.status = "failed"
                        print(f"Payment {payment_id} moved to DLQ after {outbox_event.retry_count} retries")
                    else:
                        # Keep pending for retry
                        outbox_event.status = "pending"
                    
                    outbox_event.error_message = str(e)
                    await retry_session.commit()
                    
                    # If not permanently failed, re-raise to trigger RabbitMQ retry
                    if outbox_event.status != "failed":
                        raise


@broker.subscriber(
    queue=dlq_queue,
    exchange=payments_exchange,
)
async def handle_dlq_message(message: Dict[str, Any]):
    """
    Handle messages that ended up in Dead Letter Queue.
    These are messages that failed after max retries.
    """
    payment_id = message.get("payment_id")
    print(f"DLQ: Payment {payment_id} failed permanently. Manual intervention may be required.")
    
    # Log to database or alert system
    async with async_session_maker() as session:
        result = await session.execute(
            update(OutboxEvent)
            .where(OutboxEvent.payload["payment_id"].as_string() == payment_id)
            .values(status="dlq")
        )
        await session.commit()


@app.after_startup
async def setup_queues():
    """Setup RabbitMQ queues and exchanges on startup."""
    await broker.declare_exchange(
        "payments",
        exchange_type="direct",
        durable=True,
    )
    
    await broker.declare_queue(
        settings.payments_queue,
        durable=True,
        arguments={
            "x-dead-letter-exchange": "payments",
            "x-dead-letter-routing-key": "payment.dlq",
            "x-max-length": 10000,
        },
    )
    
    await broker.declare_queue(
        settings.dlq_queue,
        durable=True,
    )
    
    await broker.declare_queue(
        "payments.new",
        durable=True,
    )
    
    print("RabbitMQ queues and exchanges configured")

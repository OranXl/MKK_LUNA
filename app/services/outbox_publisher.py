import asyncio
import logging
from datetime import datetime
from typing import Optional

from faststream.rabbit import RabbitBroker

from app.core.config import get_settings
from app.db.session import async_session_maker
from app.services.payment import PaymentService

logger = logging.getLogger(__name__)
settings = get_settings()


class OutboxPublisher:
    """
    Publishes pending outbox events to RabbitMQ.
    Implements the Transactional Outbox pattern for guaranteed delivery.
    """
    
    def __init__(self, broker: RabbitBroker):
        self.broker = broker
        self._running = False
    
    async def publish_pending_events(self, limit: int = 100) -> int:
        """
        Fetch pending outbox events and publish them to RabbitMQ.
        
        Args:
            limit: Maximum number of events to process in one batch
            
        Returns:
            Number of events successfully published
        """
        async with async_session_maker() as session:
            service = PaymentService(session)
            events = await service.get_pending_outbox_events(limit=limit)
            
            if not events:
                return 0
            
            published_count = 0
            for event in events:
                try:
                    await self._publish_event(event)
                    await service.mark_outbox_published(event.id)
                    published_count += 1
                    logger.info(f"Published outbox event {event.id}: {event.event_type}")
                except Exception as e:
                    logger.error(f"Failed to publish outbox event {event.id}: {e}")
                    await service.mark_outbox_failed(event.id, str(e))
            
            await session.commit()
            return published_count
    
    async def _publish_event(self, event) -> None:
        """
        Publish a single outbox event to RabbitMQ.
        
        Args:
            event: OutboxEvent instance to publish
        """
        # Publish to the payments.new queue via the payments exchange
        await self.broker.publish(
            message=event.payload,
            exchange="payments",
            routing_key="payments.new",
        )
    
    async def run_periodically(self, interval: float = 1.0) -> None:
        """
        Run the publisher in a loop, checking for pending events periodically.
        
        Args:
            interval: Time in seconds between each check
        """
        self._running = True
        logger.info(f"OutboxPublisher started with interval {interval}s")
        
        while self._running:
            try:
                count = await self.publish_pending_events()
                if count > 0:
                    logger.info(f"Published {count} events")
            except Exception as e:
                logger.error(f"Error in outbox publisher loop: {e}")
            
            await asyncio.sleep(interval)
    
    def stop(self) -> None:
        """Stop the publisher loop."""
        self._running = False
        logger.info("OutboxPublisher stopped")


# Global publisher instance
_publisher: Optional[OutboxPublisher] = None


def get_publisher(broker: RabbitBroker) -> OutboxPublisher:
    """Get or create the global OutboxPublisher instance."""
    global _publisher
    if _publisher is None:
        _publisher = OutboxPublisher(broker)
    return _publisher


async def start_publisher(broker: RabbitBroker, interval: float = 1.0) -> asyncio.Task:
    """
    Start the outbox publisher as a background task.
    
    Args:
        broker: RabbitBroker instance for publishing
        interval: Check interval in seconds
        
    Returns:
        asyncio.Task for the publisher loop
    """
    publisher = get_publisher(broker)
    task = asyncio.create_task(publisher.run_periodically(interval=interval))
    return task


def stop_publisher() -> None:
    """Stop the global outbox publisher."""
    if _publisher:
        _publisher.stop()

from fastapi import FastAPI
from contextlib import asynccontextmanager

from app.db.session import engine, Base
from app.models.payment import Payment, OutboxEvent  # noqa: F401


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    # Startup: create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("Database tables created")
    
    yield
    
    # Shutdown
    await engine.dispose()
    print("Database connections closed")


def create_consumer_app() -> FastAPI:
    from faststream import FastStream
    from faststream.rabbit import RabbitBroker
    from app.core.config import get_settings
    from app.consumers.payment_consumer import broker, setup_queues
    
    settings = get_settings()
    
    app = FastStream(
        broker,
        title="Payment Consumer",
        version="1.0.0",
    )
    
    return app


consumer_app = create_consumer_app()

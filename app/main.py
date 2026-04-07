from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import asyncio

from app.api.payments import router as payments_router
from app.core.config import get_settings
from app.services.outbox_publisher import start_publisher, stop_publisher
from app.db.session import engine, Base
from app.models.payment import Payment, OutboxEvent  # noqa: F401
from app.consumers.payment_consumer import broker

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    # Startup: create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("Database tables created")
    
    # Start outbox publisher
    publisher_task = await start_publisher(broker, interval=1.0)
    print("Outbox publisher started")
    
    yield
    
    # Shutdown
    stop_publisher()
    publisher_task.cancel()
    try:
        await publisher_task
    except asyncio.CancelledError:
        pass
    
    await engine.dispose()
    print("Database connections closed")


def create_app() -> FastAPI:
    app = FastAPI(
        title="Payment Processing Service",
        description="Async microservice for payment processing with webhook notifications",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include routers
    app.include_router(payments_router)

    @app.get("/health")
    async def health_check():
        return {"status": "healthy"}

    return app


app = create_app()

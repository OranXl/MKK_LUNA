"""Test fixtures and configuration."""
import asyncio
from typing import AsyncGenerator, Generator
from decimal import Decimal
from datetime import datetime
import os

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.db.session import Base, get_db
from app.models.payment import Payment, OutboxEvent
from app.core.enums import PaymentStatus
from app.core.config import Settings, get_settings


# Test database URL (using SQLite for simplicity in tests)
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

# Test API key
TEST_API_KEY = "test-api-key"


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create an instance of the default event loop for each test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="function")
def override_settings():
    """Override settings with test values."""
    def _get_test_settings() -> Settings:
        return Settings(api_key=TEST_API_KEY)
    
    # Override the get_settings function
    import app.api.payments as payments_module
    original_get_settings = payments_module.get_settings
    payments_module.get_settings = _get_test_settings
    payments_module.settings = _get_test_settings()
    
    yield
    
    # Restore original
    payments_module.get_settings = original_get_settings


@pytest_asyncio.fixture(scope="function")
async def db_engine():
    """Create a fresh database engine for each test."""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    yield engine
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def db_session(db_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create a fresh database session for each test."""
    async_session = async_sessionmaker(
        bind=db_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    
    async with async_session() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture(scope="function")
async def client(db_session: AsyncSession, override_settings) -> AsyncGenerator[AsyncClient, None]:
    """Create a test client with overridden database dependency."""
    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session
    
    app.dependency_overrides[get_db] = override_get_db
    
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac
    
    app.dependency_overrides.clear()


@pytest.fixture
def sample_payment_data() -> dict:
    """Sample payment data for testing."""
    return {
        "amount": "1000.00",
        "currency": "RUB",
        "description": "Test payment description",
        "metadata": {"order_id": "12345", "user_id": "67890"},
        "webhook_url": "https://example.com/webhook",
    }


@pytest.fixture
def sample_idempotency_key() -> str:
    """Sample idempotency key for testing."""
    return "test-idempotency-key-12345"


@pytest.fixture
def sample_api_key() -> str:
    """Sample API key for testing."""
    return TEST_API_KEY

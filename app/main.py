from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.payments import router as payments_router
from app.core.config import get_settings

settings = get_settings()


def create_app() -> FastAPI:
    app = FastAPI(
        title="Payment Processing Service",
        description="Async microservice for payment processing with webhook notifications",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
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

from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/payments"
    
    # RabbitMQ
    rabbitmq_url: str = "amqp://guest:guest@localhost:5672/"
    rabbitmq_host: str = "localhost"
    rabbitmq_port: int = 5672
    rabbitmq_user: str = "guest"
    rabbitmq_password: str = "guest"
    
    # Queues
    payments_queue: str = "payments.new"
    dlq_queue: str = "payments.dlq"
    
    # API
    api_key: str = "test-api-key-12345"
    
    # Retry settings
    max_retries: int = 3
    retry_base_delay: float = 1.0
    
    class Config:
        env_file = ".env"


@lru_cache()
def get_settings() -> Settings:
    return Settings()

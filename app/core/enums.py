from enum import Enum


class PaymentStatus(str, Enum):
    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    COMPLETED = "completed"  # Alias for succeeded for backward compatibility


class Currency(str, Enum):
    RUB = "RUB"
    USD = "USD"
    EUR = "EUR"

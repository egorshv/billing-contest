from __future__ import annotations

from enum import Enum


class OrderPaymentStatus(str, Enum):
    UNPAID = "unpaid"
    PARTIALLY_PAID = "partially_paid"
    PAID = "paid"


class PaymentType(str, Enum):
    CASH = "cash"
    ACQUIRING = "acquiring"


class PaymentStatus(str, Enum):
    PENDING = "pending"
    SUCCEEDED = "succeeded"
    PARTIALLY_REFUNDED = "partially_refunded"
    REFUNDED = "refunded"
    FAILED = "failed"


class BankStatus(str, Enum):
    CREATED = "created"
    PENDING = "pending"
    PAID = "paid"
    FAILED = "failed"
    CANCELLED = "cancelled"
    UNKNOWN = "unknown"

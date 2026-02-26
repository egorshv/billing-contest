from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.enums import OrderPaymentStatus, PaymentStatus, PaymentType


class PaymentCreateRequest(BaseModel):
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    payment_type: PaymentType


class RefundRequest(BaseModel):
    amount: Decimal | None = Field(default=None, gt=0, max_digits=12, decimal_places=2)


class PaymentResponse(BaseModel):
    id: int
    order_id: int
    payment_type: PaymentType
    amount: Decimal
    refunded_amount: Decimal
    status: PaymentStatus
    external_payment_id: str | None
    paid_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class OrderResponse(BaseModel):
    id: int
    total_amount: Decimal
    payment_status: OrderPaymentStatus
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class OrderWithPaymentsResponse(OrderResponse):
    payments: list[PaymentResponse]


class PaymentOperationResponse(BaseModel):
    order: OrderResponse
    payment: PaymentResponse


class SyncResponse(BaseModel):
    payment: PaymentResponse
    order: OrderResponse


class ReconcileResponse(BaseModel):
    processed_payments: int
    affected_orders: int

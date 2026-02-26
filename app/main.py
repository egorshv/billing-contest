from __future__ import annotations

from typing import Generator

from fastapi import Depends, FastAPI
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.bank.client import BankAPIClient
from app.bootstrap import init_db
from app.config import settings
from app.database import get_session
from app.exceptions import AppError
from app.schemas import (
    ReconcileResponse,
    OrderResponse,
    OrderWithPaymentsResponse,
    PaymentCreateRequest,
    PaymentOperationResponse,
    RefundRequest,
    SyncResponse,
)
from app.services import PaymentService


app = FastAPI(title="Billing Contest Payment Service", version="1.0.0")


@app.on_event("startup")
def startup() -> None:
    init_db()


@app.exception_handler(AppError)
async def app_error_handler(_, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.code,
            "detail": exc.message,
        },
    )


def get_bank_client() -> Generator[BankAPIClient, None, None]:
    client = BankAPIClient(
        base_url=settings.bank_api_base_url,
        timeout_seconds=settings.bank_api_timeout_seconds,
    )
    try:
        yield client
    finally:
        client.close()


def get_payment_service(
    session: Session = Depends(get_session),
    bank_client: BankAPIClient = Depends(get_bank_client),
) -> PaymentService:
    return PaymentService(session=session, bank_client=bank_client)


@app.get("/orders", response_model=list[OrderWithPaymentsResponse])
def list_orders(service: PaymentService = Depends(get_payment_service)) -> list[OrderWithPaymentsResponse]:
    orders = service.list_orders()
    return [OrderWithPaymentsResponse.model_validate(order) for order in orders]


@app.get("/orders/{order_id}", response_model=OrderWithPaymentsResponse)
def get_order(order_id: int, service: PaymentService = Depends(get_payment_service)) -> OrderWithPaymentsResponse:
    order = service.get_order(order_id)
    return OrderWithPaymentsResponse.model_validate(order)


@app.post("/orders/{order_id}/payments", response_model=PaymentOperationResponse, status_code=201)
def create_payment(
    order_id: int,
    request: PaymentCreateRequest,
    service: PaymentService = Depends(get_payment_service),
) -> PaymentOperationResponse:
    result = service.deposit(order_id=order_id, amount_raw=request.amount, payment_type=request.payment_type)
    return PaymentOperationResponse(
        order=OrderResponse.model_validate(result.order),
        payment=result.payment,
    )


@app.post("/payments/{payment_id}/refund", response_model=PaymentOperationResponse)
def refund_payment(
    payment_id: int,
    request: RefundRequest,
    service: PaymentService = Depends(get_payment_service),
) -> PaymentOperationResponse:
    result = service.refund(payment_id=payment_id, amount_raw=request.amount)
    return PaymentOperationResponse(
        order=OrderResponse.model_validate(result.order),
        payment=result.payment,
    )


@app.post("/payments/{payment_id}/sync", response_model=SyncResponse)
def sync_payment(payment_id: int, service: PaymentService = Depends(get_payment_service)) -> SyncResponse:
    payment = service.sync_payment(payment_id)
    return SyncResponse(
        payment=payment,
        order=payment.order,
    )


@app.post("/payments/reconcile", response_model=ReconcileResponse)
def reconcile_pending_payments(service: PaymentService = Depends(get_payment_service)) -> ReconcileResponse:
    processed_payments, affected_orders = service.reconcile_pending_payments()
    return ReconcileResponse(
        processed_payments=processed_payments,
        affected_orders=affected_orders,
    )

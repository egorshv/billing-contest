from __future__ import annotations

from decimal import Decimal

import pytest

from app.enums import BankStatus, OrderPaymentStatus, PaymentStatus, PaymentType
from app.exceptions import ConflictError
from app.services import PaymentService


def test_cash_payments_and_overpay_protection(session, seeded_order, bank_client):
    service = PaymentService(session=session, bank_client=bank_client)

    first = service.deposit(seeded_order.id, Decimal("40.00"), PaymentType.CASH)
    assert first.order.payment_status == OrderPaymentStatus.PARTIALLY_PAID
    assert first.payment.status == PaymentStatus.SUCCEEDED

    second = service.deposit(seeded_order.id, Decimal("60.00"), PaymentType.CASH)
    assert second.order.payment_status == OrderPaymentStatus.PAID

    with pytest.raises(ConflictError):
        service.deposit(seeded_order.id, Decimal("1.00"), PaymentType.CASH)


def test_refund_recalculates_order_status(session, seeded_order, bank_client):
    service = PaymentService(session=session, bank_client=bank_client)

    deposited = service.deposit(seeded_order.id, Decimal("100.00"), PaymentType.CASH)
    assert deposited.order.payment_status == OrderPaymentStatus.PAID

    first_refund = service.refund(deposited.payment.id, Decimal("30.00"))
    assert first_refund.payment.status == PaymentStatus.PARTIALLY_REFUNDED
    assert first_refund.order.payment_status == OrderPaymentStatus.PARTIALLY_PAID

    second_refund = service.refund(deposited.payment.id)
    assert second_refund.payment.status == PaymentStatus.REFUNDED
    assert second_refund.order.payment_status == OrderPaymentStatus.UNPAID

    with pytest.raises(ConflictError):
        service.refund(deposited.payment.id, Decimal("1.00"))


def test_acquiring_sync_can_mark_payment_as_paid(session, seeded_order, bank_client, now_utc):
    service = PaymentService(session=session, bank_client=bank_client)

    result = service.deposit(seeded_order.id, Decimal("100.00"), PaymentType.ACQUIRING)
    payment = result.payment
    assert payment.status == PaymentStatus.PENDING
    assert result.order.payment_status == OrderPaymentStatus.UNPAID

    bank_client.set_status(payment.external_payment_id, BankStatus.PAID, paid_at=now_utc)

    synced = service.sync_payment(payment.id)
    assert synced.status == PaymentStatus.SUCCEEDED
    assert synced.order.payment_status == OrderPaymentStatus.PAID


def test_failed_pending_acquiring_frees_amount_for_new_deposit(session, seeded_order, bank_client):
    service = PaymentService(session=session, bank_client=bank_client)

    acquiring = service.deposit(seeded_order.id, Decimal("100.00"), PaymentType.ACQUIRING)
    assert acquiring.payment.status == PaymentStatus.PENDING

    bank_client.set_status(acquiring.payment.external_payment_id, BankStatus.FAILED)

    cash = service.deposit(seeded_order.id, Decimal("100.00"), PaymentType.CASH)
    assert cash.payment.status == PaymentStatus.SUCCEEDED
    assert cash.order.payment_status == OrderPaymentStatus.PAID

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.bank.client import BankAPIClient
from app.enums import BankStatus, OrderPaymentStatus, PaymentStatus, PaymentType
from app.exceptions import ConflictError, NotFoundError, ValidationError
from app.models import BankPaymentState, Order, Payment


MONEY_STEP = Decimal("0.01")
ZERO_MONEY = Decimal("0.00")


@dataclass(frozen=True)
class OrderPaymentResult:
    order: Order
    payment: Payment


class PaymentService:
    def __init__(self, session: Session, bank_client: BankAPIClient):
        self.session = session
        self.bank_client = bank_client

    def list_orders(self) -> list[Order]:
        return list(
            self.session.scalars(
                select(Order)
                .options(selectinload(Order.payments).selectinload(Payment.bank_state))
                .order_by(Order.id)
            )
        )

    def get_order(self, order_id: int) -> Order:
        order = self.session.scalar(
            select(Order)
            .options(selectinload(Order.payments).selectinload(Payment.bank_state))
            .where(Order.id == order_id)
        )
        if not order:
            raise NotFoundError(f"Order {order_id} not found")
        return order

    def deposit(self, order_id: int, amount_raw: Decimal, payment_type: PaymentType) -> OrderPaymentResult:
        amount = self._normalize_positive_amount(amount_raw)
        self.sync_order_acquiring_payments(order_id, fail_silently=True)

        order = self.get_order(order_id)
        reserved_amount = self._reserved_amount(order)
        if reserved_amount + amount > order.total_amount:
            raise ConflictError(
                "Total amount across successful and pending payments cannot exceed order total amount"
            )

        payment_status = PaymentStatus.SUCCEEDED if payment_type == PaymentType.CASH else PaymentStatus.PENDING
        external_payment_id: str | None = None

        if payment_type == PaymentType.ACQUIRING:
            external_payment_id = self.bank_client.start_acquiring(order_id=order.id, amount=amount)

        payment = Payment(
            order=order,
            payment_type=payment_type,
            amount=amount,
            refunded_amount=ZERO_MONEY,
            status=payment_status,
            external_payment_id=external_payment_id,
            paid_at=datetime.now(timezone.utc) if payment_status == PaymentStatus.SUCCEEDED else None,
        )
        self.session.add(payment)
        self.session.flush()

        if payment_type == PaymentType.ACQUIRING:
            bank_state = BankPaymentState(
                payment_id=payment.id,
                bank_payment_id=external_payment_id,
                bank_amount=amount,
                bank_status=BankStatus.CREATED,
            )
            self.session.add(bank_state)

        self._recalculate_order_status(order)
        self.session.commit()
        self.session.refresh(order)
        self.session.refresh(payment)

        return OrderPaymentResult(order=order, payment=payment)

    def refund(self, payment_id: int, amount_raw: Decimal | None = None) -> OrderPaymentResult:
        payment = self._get_payment(payment_id)

        if payment.payment_type == PaymentType.ACQUIRING:
            self.sync_payment(payment_id)
            payment = self._get_payment(payment_id)

        refundable_amount = payment.amount - payment.refunded_amount
        if refundable_amount <= ZERO_MONEY:
            raise ConflictError(f"Payment {payment.id} has no refundable amount")

        refund_amount = refundable_amount if amount_raw is None else self._normalize_positive_amount(amount_raw)
        if refund_amount > refundable_amount:
            raise ConflictError(
                f"Refund amount {refund_amount} exceeds available refundable amount {refundable_amount}"
            )

        if payment.status not in {
            PaymentStatus.SUCCEEDED,
            PaymentStatus.PARTIALLY_REFUNDED,
            PaymentStatus.REFUNDED,
        }:
            raise ConflictError(f"Payment {payment.id} cannot be refunded in status {payment.status.value}")

        payment.refunded_amount = (payment.refunded_amount + refund_amount).quantize(MONEY_STEP, rounding=ROUND_HALF_UP)
        if payment.refunded_amount == payment.amount:
            payment.status = PaymentStatus.REFUNDED
        else:
            payment.status = PaymentStatus.PARTIALLY_REFUNDED

        order = payment.order
        self._recalculate_order_status(order)
        self.session.commit()
        self.session.refresh(order)
        self.session.refresh(payment)

        return OrderPaymentResult(order=order, payment=payment)

    def sync_payment(self, payment_id: int) -> Payment:
        payment = self._get_payment(payment_id)
        if payment.payment_type != PaymentType.ACQUIRING:
            return payment

        try:
            self._sync_acquiring_payment(payment, fail_silently=False)
        except Exception:
            self.session.commit()
            raise
        self._recalculate_order_status(payment.order)
        self.session.commit()
        self.session.refresh(payment)
        self.session.refresh(payment.order)

        return payment

    def sync_order_acquiring_payments(self, order_id: int, fail_silently: bool) -> None:
        order = self.get_order(order_id)
        touched = False

        for payment in order.payments:
            if payment.payment_type != PaymentType.ACQUIRING:
                continue
            if payment.status != PaymentStatus.PENDING:
                continue
            touched = True
            self._sync_acquiring_payment(payment, fail_silently=fail_silently)

        if touched:
            self._recalculate_order_status(order)
            self.session.commit()

    def reconcile_pending_payments(self) -> tuple[int, int]:
        pending_payments = list(
            self.session.scalars(
                select(Payment)
                .options(selectinload(Payment.order).selectinload(Order.payments).selectinload(Payment.bank_state))
                .where(Payment.payment_type == PaymentType.ACQUIRING, Payment.status == PaymentStatus.PENDING)
            )
        )
        if not pending_payments:
            return 0, 0

        affected_orders: dict[int, Order] = {}
        for payment in pending_payments:
            affected_orders[payment.order.id] = payment.order
            self._sync_acquiring_payment(payment, fail_silently=True)

        for order in affected_orders.values():
            self._recalculate_order_status(order)

        self.session.commit()
        return len(pending_payments), len(affected_orders)

    def _sync_acquiring_payment(self, payment: Payment, fail_silently: bool) -> bool:
        if not payment.external_payment_id or not payment.bank_state:
            raise ConflictError(f"Acquiring payment {payment.id} has no linked bank state")

        try:
            snapshot = self.bank_client.check_acquiring(payment.external_payment_id)
        except Exception as exc:
            payment.bank_state.last_checked_at = datetime.now(timezone.utc)
            payment.bank_state.last_error = str(exc)
            if fail_silently:
                self.session.flush()
                return False
            raise

        if snapshot.bank_payment_id != payment.external_payment_id:
            raise ConflictError(
                f"Bank payment id mismatch for payment {payment.id}: expected {payment.external_payment_id}, got {snapshot.bank_payment_id}"
            )

        if snapshot.amount != payment.amount:
            raise ConflictError(
                f"Bank amount mismatch for payment {payment.id}: expected {payment.amount}, got {snapshot.amount}"
            )

        payment.bank_state.bank_amount = snapshot.amount
        payment.bank_state.bank_status = snapshot.status
        payment.bank_state.bank_paid_at = snapshot.paid_at
        payment.bank_state.last_checked_at = datetime.now(timezone.utc)
        payment.bank_state.last_error = None

        previous_status = payment.status

        if snapshot.status == BankStatus.PAID:
            payment.status = PaymentStatus.SUCCEEDED
            payment.paid_at = snapshot.paid_at or payment.paid_at or datetime.now(timezone.utc)
        elif snapshot.status in {BankStatus.FAILED, BankStatus.CANCELLED}:
            payment.status = PaymentStatus.FAILED

        self.session.flush()
        return previous_status != payment.status

    def _get_payment(self, payment_id: int) -> Payment:
        payment = self.session.scalar(
            select(Payment)
            .options(selectinload(Payment.order).selectinload(Order.payments).selectinload(Payment.bank_state))
            .where(Payment.id == payment_id)
        )
        if not payment:
            raise NotFoundError(f"Payment {payment_id} not found")
        return payment

    def _reserved_amount(self, order: Order) -> Decimal:
        reserved = ZERO_MONEY
        for payment in order.payments:
            if payment.status == PaymentStatus.FAILED:
                continue
            if payment.status == PaymentStatus.PENDING:
                reserved += payment.amount
            else:
                reserved += payment.amount - payment.refunded_amount
        return reserved.quantize(MONEY_STEP, rounding=ROUND_HALF_UP)

    def _paid_amount(self, order: Order) -> Decimal:
        paid = ZERO_MONEY
        for payment in order.payments:
            if payment.status in {
                PaymentStatus.SUCCEEDED,
                PaymentStatus.PARTIALLY_REFUNDED,
                PaymentStatus.REFUNDED,
            }:
                paid += payment.amount - payment.refunded_amount
        return paid.quantize(MONEY_STEP, rounding=ROUND_HALF_UP)

    def _recalculate_order_status(self, order: Order) -> None:
        paid_amount = self._paid_amount(order)

        if paid_amount <= ZERO_MONEY:
            order.payment_status = OrderPaymentStatus.UNPAID
            return

        if paid_amount >= order.total_amount:
            order.payment_status = OrderPaymentStatus.PAID
            return

        order.payment_status = OrderPaymentStatus.PARTIALLY_PAID

    @staticmethod
    def _normalize_positive_amount(value: Decimal | str | int | float) -> Decimal:
        try:
            amount = Decimal(str(value)).quantize(MONEY_STEP, rounding=ROUND_HALF_UP)
        except (InvalidOperation, ValueError, TypeError) as exc:
            raise ValidationError("Amount must be a decimal number") from exc

        if amount <= ZERO_MONEY:
            raise ValidationError("Amount must be greater than zero")

        return amount

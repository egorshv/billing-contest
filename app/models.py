from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, Enum, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.enums import BankStatus, OrderPaymentStatus, PaymentStatus, PaymentType


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    payment_status: Mapped[OrderPaymentStatus] = mapped_column(
        Enum(OrderPaymentStatus, native_enum=False),
        nullable=False,
        default=OrderPaymentStatus.UNPAID,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    payments: Mapped[list["Payment"]] = relationship(back_populates="order", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint("total_amount > 0", name="ck_orders_total_amount_positive"),
    )


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True)
    payment_type: Mapped[PaymentType] = mapped_column(Enum(PaymentType, native_enum=False), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    refunded_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    status: Mapped[PaymentStatus] = mapped_column(Enum(PaymentStatus, native_enum=False), nullable=False)
    external_payment_id: Mapped[str | None] = mapped_column(String(128), nullable=True, unique=True)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    order: Mapped[Order] = relationship(back_populates="payments")
    bank_state: Mapped["BankPaymentState | None"] = relationship(back_populates="payment", uselist=False)

    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_payments_amount_positive"),
        CheckConstraint("refunded_amount >= 0", name="ck_payments_refunded_non_negative"),
        CheckConstraint("refunded_amount <= amount", name="ck_payments_refunded_not_gt_amount"),
    )


class BankPaymentState(Base):
    __tablename__ = "bank_payment_states"

    id: Mapped[int] = mapped_column(primary_key=True)
    payment_id: Mapped[int] = mapped_column(ForeignKey("payments.id", ondelete="CASCADE"), nullable=False, unique=True)
    bank_payment_id: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    bank_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    bank_status: Mapped[BankStatus] = mapped_column(
        Enum(BankStatus, native_enum=False),
        nullable=False,
        default=BankStatus.CREATED,
    )
    bank_paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text(), nullable=True)

    payment: Mapped[Payment] = relationship(back_populates="bank_state")

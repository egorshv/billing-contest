from __future__ import annotations

from decimal import Decimal

from sqlalchemy import func, select

from app.database import Base, SessionLocal, engine
from app.enums import OrderPaymentStatus
from app.models import Order


DEFAULT_ORDER_AMOUNTS = [Decimal("1000.00"), Decimal("2500.00"), Decimal("999.99")]


def init_db() -> None:
    Base.metadata.create_all(bind=engine)

    with SessionLocal() as session:
        existing_orders = session.scalar(select(func.count(Order.id)))
        if existing_orders and existing_orders > 0:
            return

        for amount in DEFAULT_ORDER_AMOUNTS:
            session.add(
                Order(
                    total_amount=amount,
                    payment_status=OrderPaymentStatus.UNPAID,
                )
            )
        session.commit()

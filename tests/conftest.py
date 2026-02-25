from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.bank_client import BankPaymentSnapshot
from app.database import Base
from app.enums import BankStatus, OrderPaymentStatus
from app.models import Order


class FakeBankClient:
    def __init__(self):
        self._counter = 1
        self._statuses: dict[str, BankPaymentSnapshot] = {}

    def start_acquiring(self, order_id: int, amount: Decimal) -> str:
        payment_id = f"BANK-{self._counter}"
        self._counter += 1
        self._statuses[payment_id] = BankPaymentSnapshot(
            bank_payment_id=payment_id,
            amount=amount,
            status=BankStatus.PENDING,
            paid_at=None,
        )
        return payment_id

    def check_acquiring(self, bank_payment_id: str) -> BankPaymentSnapshot:
        return self._statuses[bank_payment_id]

    def set_status(
        self,
        bank_payment_id: str,
        status: BankStatus,
        paid_at: datetime | None = None,
    ) -> None:
        previous = self._statuses[bank_payment_id]
        self._statuses[bank_payment_id] = BankPaymentSnapshot(
            bank_payment_id=previous.bank_payment_id,
            amount=previous.amount,
            status=status,
            paid_at=paid_at,
        )


@pytest.fixture
def session() -> Session:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
    Base.metadata.create_all(bind=engine)

    with SessionLocal() as session:
        yield session


@pytest.fixture
def seeded_order(session: Session) -> Order:
    order = Order(total_amount=Decimal("100.00"), payment_status=OrderPaymentStatus.UNPAID)
    session.add(order)
    session.commit()
    session.refresh(order)
    return order


@pytest.fixture
def bank_client() -> FakeBankClient:
    return FakeBankClient()


@pytest.fixture
def now_utc() -> datetime:
    return datetime.now(timezone.utc)

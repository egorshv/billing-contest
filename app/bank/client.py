from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

import httpx

from app.bank.base_client import BaseBankAPIClient
from app.bank.data_wrapper import BankAPIResponseWrapper
from app.enums import BankStatus


@dataclass(frozen=True)
class BankPaymentSnapshot:
    bank_payment_id: str
    amount: Decimal
    status: BankStatus
    paid_at: datetime | None


class BankAPIClient(BaseBankAPIClient):
    def __init__(self, base_url: str, timeout_seconds: float):
        super().__init__(base_url, timeout_seconds)

    def close(self) -> None:
        self._client.close()

    def start_acquiring(self, order_id: int, amount: Decimal) -> str:
        payload = {"order_number": str(order_id), "amount": str(amount)}
        data = self._post_json("/acquiring_start", payload)

        response_wrapper = BankAPIResponseWrapper(data)
        response_wrapper.validate_data_for_start_acquiring()
        return response_wrapper.get_bank_payment_id()

    def check_acquiring(self, bank_payment_id: str) -> BankPaymentSnapshot:
        data = self._post_json("/acquiring_check", {"bank_payment_id": bank_payment_id})

        response_wrapper = BankAPIResponseWrapper(data)
        response_wrapper.validate_data_for_check_acquiring(bank_payment_id)

        returned_payment_id = response_wrapper.get_bank_payment_id()

        amount = response_wrapper.get_amount()

        status = self._map_status(data.get("status"))
        paid_at = self._parse_dt(data.get("paid_at") or data.get("paid_datetime"))

        return BankPaymentSnapshot(
            bank_payment_id=returned_payment_id,
            amount=amount,
            status=status,
            paid_at=paid_at,
        )

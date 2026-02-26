from decimal import Decimal, InvalidOperation
from typing import Any

from app.exceptions import ExternalServiceError, BankPaymentNotFoundError


class BankAPIResponseWrapper:
    def __init__(self, data: Any):
        self._data = data


    def validate_data_for_start_acquiring(self) -> None:
        if isinstance(self._data, str):
            raise ExternalServiceError(f"Bank acquiring_start failed: {self._data}")

        if not isinstance(self._data, dict):
            raise ExternalServiceError("Bank acquiring_start returned invalid payload")

        if self._data.get("error"):
            raise ExternalServiceError(f"Bank acquiring_start failed: {self._data['error']}")

        return

    def validate_data_for_check_acquiring(self, bank_payment_id: str) -> None:
        if isinstance(self._data, str):
            if "не найден" in self._data.lower() or "not found" in self._data.lower():
                raise BankPaymentNotFoundError(f"Bank payment {bank_payment_id} not found")
            raise ExternalServiceError(f"Bank acquiring_check failed: {self._data}")

        if not isinstance(self._data, dict):
            raise ExternalServiceError("Bank acquiring_check returned invalid payload")

        if self._data.get("error"):
            error_message = str(self._data["error"])
            if "не найден" in error_message.lower() or "not found" in error_message.lower():
                raise BankPaymentNotFoundError(f"Bank payment {bank_payment_id} not found")
            raise ExternalServiceError(f"Bank acquiring_check failed: {error_message}")
        return

    def get_bank_payment_id(self) -> str:
        bank_payment_id = self._data.get("bank_payment_id") or self._data.get("payment_id") or self._data.get("id")
        if not bank_payment_id:
            raise ExternalServiceError("Bank response has no payment id")
        return str(bank_payment_id)

    def get_amount(self) -> Decimal:
        amount_raw = self._data.get("amount")
        try:
            return Decimal(str(amount_raw))
        except (InvalidOperation, TypeError) as exc:
            raise ExternalServiceError("Bank acquiring returned invalid amount") from exc

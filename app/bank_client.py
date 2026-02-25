from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation

import httpx

from app.enums import BankStatus
from app.exceptions import BankPaymentNotFoundError, ExternalServiceError


@dataclass(frozen=True)
class BankPaymentSnapshot:
    bank_payment_id: str
    amount: Decimal
    status: BankStatus
    paid_at: datetime | None


class BankApiClient:
    def __init__(
        self,
        base_url: str,
        timeout_seconds: float,
        http_client: httpx.Client | None = None,
    ):
        self._owns_client = http_client is None
        self._client = http_client or httpx.Client(base_url=base_url, timeout=timeout_seconds)

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def start_acquiring(self, order_id: int, amount: Decimal) -> str:
        payload = {"order_number": str(order_id), "amount": str(amount)}
        data = self._post_json("/acquiring_start", payload)

        if isinstance(data, str):
            raise ExternalServiceError(f"Bank acquiring_start failed: {data}")

        if not isinstance(data, dict):
            raise ExternalServiceError("Bank acquiring_start returned invalid payload")

        if data.get("error"):
            raise ExternalServiceError(f"Bank acquiring_start failed: {data['error']}")

        bank_payment_id = data.get("bank_payment_id") or data.get("payment_id") or data.get("id")
        if not bank_payment_id:
            raise ExternalServiceError("Bank acquiring_start response has no payment id")

        return str(bank_payment_id)

    def check_acquiring(self, bank_payment_id: str) -> BankPaymentSnapshot:
        data = self._post_json("/acquiring_check", {"bank_payment_id": bank_payment_id})

        if isinstance(data, str):
            if "не найден" in data.lower() or "not found" in data.lower():
                raise BankPaymentNotFoundError(f"Bank payment {bank_payment_id} not found")
            raise ExternalServiceError(f"Bank acquiring_check failed: {data}")

        if not isinstance(data, dict):
            raise ExternalServiceError("Bank acquiring_check returned invalid payload")

        if data.get("error"):
            error_message = str(data["error"])
            if "не найден" in error_message.lower() or "not found" in error_message.lower():
                raise BankPaymentNotFoundError(f"Bank payment {bank_payment_id} not found")
            raise ExternalServiceError(f"Bank acquiring_check failed: {error_message}")

        returned_payment_id = str(data.get("bank_payment_id") or data.get("payment_id") or "")
        if not returned_payment_id:
            raise ExternalServiceError("Bank acquiring_check response has no payment id")

        amount_raw = data.get("amount")
        try:
            amount = Decimal(str(amount_raw))
        except (InvalidOperation, TypeError) as exc:
            raise ExternalServiceError("Bank acquiring_check returned invalid amount") from exc

        status = self._map_status(data.get("status"))
        paid_at = self._parse_dt(data.get("paid_at") or data.get("paid_datetime"))

        return BankPaymentSnapshot(
            bank_payment_id=returned_payment_id,
            amount=amount,
            status=status,
            paid_at=paid_at,
        )

    def _post_json(self, path: str, json_payload: dict) -> dict | str:
        try:
            response = self._client.post(path, json=json_payload)
        except httpx.TimeoutException as exc:
            raise ExternalServiceError(f"Bank API timeout on {path}") from exc
        except httpx.HTTPError as exc:
            raise ExternalServiceError(f"Bank API transport error on {path}") from exc

        if response.status_code >= 500:
            raise ExternalServiceError(f"Bank API is unavailable on {path}")

        if response.status_code >= 400:
            try:
                data = response.json()
            except ValueError:
                data = response.text
            raise ExternalServiceError(f"Bank API returned HTTP {response.status_code}: {data}")

        try:
            return response.json()
        except ValueError as exc:
            raise ExternalServiceError(f"Bank API returned non-JSON on {path}") from exc

    @staticmethod
    def _map_status(raw_status: object) -> BankStatus:
        normalized = str(raw_status or "").strip().lower()
        mapping = {
            "created": BankStatus.CREATED,
            "new": BankStatus.CREATED,
            "pending": BankStatus.PENDING,
            "processing": BankStatus.PENDING,
            "paid": BankStatus.PAID,
            "succeeded": BankStatus.PAID,
            "success": BankStatus.PAID,
            "failed": BankStatus.FAILED,
            "error": BankStatus.FAILED,
            "cancelled": BankStatus.CANCELLED,
            "canceled": BankStatus.CANCELLED,
        }
        return mapping.get(normalized, BankStatus.UNKNOWN)

    @staticmethod
    def _parse_dt(raw_dt: object) -> datetime | None:
        if not raw_dt:
            return None

        dt_value = str(raw_dt)
        if dt_value.endswith("Z"):
            dt_value = dt_value.replace("Z", "+00:00")

        try:
            return datetime.fromisoformat(dt_value)
        except ValueError:
            return None

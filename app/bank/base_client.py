import httpx
from datetime import datetime
from typing import Any

from app.enums import BankStatus
from app.exceptions import ExternalServiceError


class BaseBankAPIClient:
    def __init__(self, base_url: str, timeout_seconds: float) -> None:
        self._client = httpx.Client(base_url=base_url, timeout=timeout_seconds)

    def _post_json(self, path: str, json_payload: dict, httpx=None) -> dict | str:
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
    def _map_status(raw_status: Any) -> BankStatus:
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
    def _parse_dt(raw_dt: Any) -> datetime | None:
        if not raw_dt:
            return None

        dt_value = str(raw_dt)
        if dt_value.endswith("Z"):
            dt_value = dt_value.replace("Z", "+00:00")

        try:
            return datetime.fromisoformat(dt_value)
        except ValueError:
            return None
from __future__ import annotations

from dataclasses import dataclass
import os


@dataclass(frozen=True)
class Settings:
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./billing.db")
    bank_api_base_url: str = os.getenv("BANK_API_BASE_URL", "https://bank.api")
    bank_api_timeout_seconds: float = float(os.getenv("BANK_API_TIMEOUT_SECONDS", "5.0"))


settings = Settings()

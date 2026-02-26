from __future__ import annotations


class AppError(Exception):
    status_code = 400
    code = "app_error"

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


class NotFoundError(AppError):
    status_code = 404
    code = "not_found"


class ValidationError(AppError):
    status_code = 400
    code = "validation_error"


class ConflictError(AppError):
    status_code = 409
    code = "conflict"


class ExternalServiceError(AppError):
    status_code = 502
    code = "external_service_error"


class BankPaymentNotFoundError(ExternalServiceError):
    status_code = 409
    code = "bank_payment_not_found"

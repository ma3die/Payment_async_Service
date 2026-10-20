class BaseAppException(Exception):
    status_code: int = 400
    detail: str = ""

    def __init__(self, detail: str | None = None):
        if detail:
            self.detail = detail
        super().__init__(self.detail)


class UnauthorizedError(BaseAppException):
    status_code = 401
    detail = "Неверный API-ключ"


class PaymentNotFoundError(BaseAppException):
    status_code = 404
    detail = "Платёж не найден"


class IdempotencyConflictError(BaseAppException):
    status_code = 409
    detail = "Ключ идемпотентности уже использован с другим телом запроса"


class InvalidIdempotencyKeyError(BaseAppException):
    status_code = 422
    detail = "Idempotency-Key не может быть пустым"


class RetryableError(Exception):
    """Ошибка, после которой обработку сообщения можно повторить."""


class WebhookDeliveryError(RetryableError):
    """Сеть, таймаут, 429 или 5xx. Отправку можно повторить."""


class WebhookRejectedError(Exception):
    """Клиент отверг уведомление. Повтор тех же данных ничего не изменит."""

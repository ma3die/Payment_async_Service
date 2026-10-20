import hashlib
import json

from schemas.payment import PaymentCreate


def payment_request_hash(data: PaymentCreate) -> str:
    """sha256 от полей платежа, ключи metadata сортируются."""
    canonical = {
        "amount": format(data.amount, "f"),
        "currency": data.currency.value,
        "description": data.description,
        "metadata": data.metadata,
        "webhook_url": str(data.webhook_url),
    }
    # убирает пробелы, сортирует ключи, чтобы при одинаковых данных хеш был один и тот же
    raw = json.dumps(canonical, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()

from uuid import uuid4

import pytest

from config import settings

PAYMENTS_URL = f"{settings.api.v1.prefix}/payments"


def _body(amount: str = "10.50") -> dict:
    return {
        "amount": amount,
        "currency": "RUB",
        "description": "Заказ",
        "metadata": {"order_id": "1"},
        "webhook_url": "https://client.test/hook",
    }


def _headers(idempotency_key: str = "order-1") -> dict:
    return {
        "X-API-Key": settings.security.API_KEY,
        "Idempotency-Key": idempotency_key,
    }


@pytest.mark.asyncio
async def test_create_payment_requires_api_key(client):
    response = await client.post(PAYMENTS_URL, json=_body())

    assert response.status_code == 401
    assert response.json()["detail"] == "Неверный API-ключ"


@pytest.mark.asyncio
async def test_same_idempotency_key_returns_the_same_payment(client):
    headers = _headers()
    first = await client.post(PAYMENTS_URL, json=_body(), headers=headers)
    second = await client.post(PAYMENTS_URL, json=_body(), headers=headers)

    assert first.status_code == 202
    assert second.status_code == 202
    assert first.json()["payment_id"] == second.json()["payment_id"]
    assert first.json()["status"] == "pending"


@pytest.mark.asyncio
async def test_same_key_with_different_body_returns_conflict(client):
    headers = _headers()
    created = await client.post(PAYMENTS_URL, json=_body("10.50"), headers=headers)
    conflict = await client.post(PAYMENTS_URL, json=_body("11.00"), headers=headers)

    assert created.status_code == 202
    assert conflict.status_code == 409
    assert conflict.json()["detail"] == "Ключ идемпотентности уже использован с другим телом запроса"


@pytest.mark.asyncio
async def test_unknown_payment_returns_not_found(client):
    response = await client.get(f"{PAYMENTS_URL}/{uuid4()}", headers=_headers())

    assert response.status_code == 404
    assert response.json()["detail"] == "Платёж не найден"

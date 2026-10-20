from decimal import Decimal

import pytest
from pydantic import ValidationError

from core.security import api_keys_match
from enums.payment import Currency
from schemas.payment import PaymentCreate


def test_api_keys_match_ignores_length_difference():
    assert api_keys_match("dev-api-key", "dev-api-key") is True
    assert api_keys_match("short", "dev-api-key") is False


def test_payment_create_rejects_non_positive_amount():
    with pytest.raises(ValidationError):
        PaymentCreate(
            amount=Decimal(0),
            currency=Currency.RUB,
            description="Заказ",
            webhook_url="https://client.test/hook",
        )


def test_payment_create_accepts_money_as_string():
    payment = PaymentCreate(
        amount="10.50",
        currency="EUR",
        description="Заказ",
        metadata={"source": "api"},
        webhook_url="https://client.test/hook",
    )

    assert payment.amount == Decimal("10.50")
    assert payment.currency is Currency.EUR
    assert payment.description == "Заказ"


def test_payment_create_strips_description_and_rejects_float_amount():
    payment = PaymentCreate(
        amount="10.50",
        currency=Currency.RUB,
        description="  Заказ  ",
        webhook_url="https://client.test/hook",
    )
    assert payment.description == "Заказ"

    with pytest.raises(ValidationError):
        PaymentCreate(
            amount=19.99,
            currency=Currency.RUB,
            description="Заказ",
            webhook_url="https://client.test/hook",
        )


def test_payment_create_rejects_blank_description_long_url_and_huge_metadata():
    with pytest.raises(ValidationError):
        PaymentCreate(
            amount="10.00",
            currency=Currency.RUB,
            description="   ",
            webhook_url="https://client.test/hook",
        )
    with pytest.raises(ValidationError):
        PaymentCreate(
            amount="10.00",
            currency=Currency.RUB,
            description="Заказ",
            webhook_url="https://client.test/" + ("a" * 2100),
        )
    with pytest.raises(ValidationError):
        PaymentCreate(
            amount="10.00",
            currency=Currency.RUB,
            description="Заказ",
            metadata={"blob": "x" * 5000},
            webhook_url="https://client.test/hook",
        )

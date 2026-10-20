import httpx
import pytest

from core.exceptions import WebhookDeliveryError, WebhookRejectedError
from enums.payment import Currency, PaymentStatus
from schemas.payment import WebhookPayload
from services.webhook_sender import WebhookSender


def _payload() -> WebhookPayload:
    return WebhookPayload(
        payment_id="b6f0c2d4-6a0e-4d3a-9c1b-1d2e3f4a5b6c",
        status=PaymentStatus.SUCCEEDED,
        amount="10.50",
        currency=Currency.RUB,
        processed_at="2026-10-19T10:00:00Z",
    )


@pytest.mark.asyncio
async def test_webhook_sender_posts_json():
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        await WebhookSender(client).send("https://client.test/hook", _payload())

    assert seen[0].url == "https://client.test/hook"
    assert b"10.50" in seen[0].content


@pytest.mark.asyncio
async def test_webhook_sender_raises_on_http_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(WebhookDeliveryError):
            await WebhookSender(client).send("https://client.test/hook", _payload())


@pytest.mark.asyncio
@pytest.mark.parametrize("status_code", [429, 503])
async def test_webhook_sender_retries_temporary_status(status_code: int):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(WebhookDeliveryError):
            await WebhookSender(client).send("https://client.test/hook", _payload())


@pytest.mark.asyncio
@pytest.mark.parametrize("status_code", [302, 404])
async def test_webhook_sender_does_not_retry_client_status(status_code: int):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(WebhookRejectedError):
            await WebhookSender(client).send("https://client.test/hook", _payload())

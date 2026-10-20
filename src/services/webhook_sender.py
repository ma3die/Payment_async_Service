import httpx

from core.exceptions import WebhookDeliveryError, WebhookRejectedError
from schemas.payment import WebhookPayload


class WebhookSender:
    """Один POST на webhook клиента. Повторы временных ошибок делает вызывающий код."""

    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client

    async def send(self, url: str, payload: WebhookPayload) -> None:
        try:
            response = await self._client.post(url, json=payload.model_dump(mode="json"))
        except httpx.HTTPError as exc:
            raise WebhookDeliveryError("Не удалось доставить webhook") from exc

        if 200 <= response.status_code < 300:
            return
        if response.status_code == 429 or response.status_code >= 500:
            raise WebhookDeliveryError(f"Webhook ответил {response.status_code}")
        raise WebhookRejectedError(f"Webhook отверг уведомление со статусом {response.status_code}")

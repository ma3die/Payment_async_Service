## Payment Service

Все чувствительные данные намеренно оставлено в проекте, включая файл `.env`

Асинхронный сервис процессинга платежей. API принимает платёж, в той же транзакции пишет событие в outbox, consumer забирает его из RabbitMQ, эмулирует платёжный шлюз и отправляет webhook.

### Стек

Python 3.11+, FastAPI, Pydantic v2, SQLAlchemy 2.0, PostgreSQL, Alembic, RabbitMQ, FastStream, httpx, Docker Compose.

### Запуск

```bash
docker compose up --build
```

- API и Swagger: http://127.0.0.1:8001/docs
- RabbitMQ Management: http://127.0.0.1:15672 (`payment` / `payment`)
- PostgreSQL с хоста: `localhost:5433`

Ключ по умолчанию задаётся в `.env` как `API_KEY`. Для локального примера ниже используется `dev-api-key`.

### Создание платежа

```bash
curl.exe -X POST http://127.0.0.1:8001/api/v1/payments ^
  -H "Content-Type: application/json" ^
  -H "X-API-Key: dev-api-key" ^
  -H "Idempotency-Key: order-1001" ^
  -d "{\"amount\": \"1500.50\", \"currency\": \"RUB\", \"description\": \"Заказ 1001\", \"metadata\": {\"order_id\": \"1001\"}, \"webhook_url\": \"https://example.com/webhook\"}"
```

Ответ `202 Accepted`:

```json
{"payment_id": "...", "status": "pending", "created_at": "..."}
```

Повтор с тем же `Idempotency-Key` и тем же телом возвращает уже созданный платёж. Другое тело с тем же ключом отвечает `409`. Сумму передавайте строкой: `"1500.50"`.

### Получение платежа

```bash
curl.exe http://127.0.0.1:8001/api/v1/payments/{payment_id} -H "X-API-Key: dev-api-key"
```

### Что происходит после 202

1. Строки `payments` и `outbox` сохраняются одной транзакцией.
2. Consumer публикует pending-события в exchange `payments` с ключом `payments.new`.
3. Обработчик ждёт 2–5 секунд. С вероятностью 90% статус становится `succeeded`, иначе `failed`.
4. На `webhook_url` уходит POST с `payment_id`, `status`, `amount`, `currency`, `processed_at`.
5. Сеть, таймаут, `429` и `5xx` повторяются до 3 раз с паузами 1 с и 2 с. `4xx` и редирект сразу отправляют сообщение в `payments.new.dlq`. Статус платежа к этому моменту уже записан.

Очереди видны в RabbitMQ Management. Пока webhook недоступен, тестовое сообщение закончит в DLQ, а статус платежа уже будет записан.

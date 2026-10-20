from faststream.rabbit import ExchangeType, RabbitExchange, RabbitQueue

from config import settings

payments_exchange = RabbitExchange(
    name=settings.rabbit.PAYMENTS_EXCHANGE,
    type=ExchangeType.DIRECT,
    durable=True,
)
dead_letter_exchange = RabbitExchange(
    name=settings.rabbit.PAYMENTS_DLX,
    type=ExchangeType.DIRECT,
    durable=True,
)
payments_queue = RabbitQueue(
    name=settings.rabbit.PAYMENTS_QUEUE,
    durable=True,
    routing_key=settings.rabbit.PAYMENTS_ROUTING_KEY,
    arguments={
        "x-dead-letter-exchange": settings.rabbit.PAYMENTS_DLX,
        "x-dead-letter-routing-key": settings.rabbit.PAYMENTS_ROUTING_KEY,
    },
)
dead_letter_queue = RabbitQueue(
    name=settings.rabbit.PAYMENTS_DLQ,
    durable=True,
    routing_key=settings.rabbit.PAYMENTS_ROUTING_KEY,
)

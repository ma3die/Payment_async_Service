from faststream.rabbit import RabbitBroker

from broker.topology import dead_letter_exchange, dead_letter_queue
from config import settings

broker = RabbitBroker(settings.rabbit.RABBITMQ_URL)


async def declare_topology() -> None:
    """Объявляет dead-letter exchange и очередь. Основную очередь объявляет consumer."""
    exchange = await broker.declare_exchange(dead_letter_exchange)
    queue = await broker.declare_queue(dead_letter_queue)
    await queue.bind(exchange, routing_key=settings.rabbit.PAYMENTS_ROUTING_KEY)

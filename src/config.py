import logging
import uuid
from pathlib import Path
from urllib.parse import quote, quote_plus

from dotenv import load_dotenv
from pydantic import computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict

from logger_config import make_logger

load_dotenv()
BASE_DIR: Path = Path(__file__).parent


class CustomBaseSettings(BaseSettings):
    model_config = SettingsConfigDict(
        validate_default=False,
        case_sensitive=False,
        env_file=".env",
        extra="allow"
    )


class ApiV1Prefix(CustomBaseSettings):
    prefix: str = "/api/v1"


class ApiPrefix(CustomBaseSettings):
    v1: ApiV1Prefix = ApiV1Prefix()


class BaseAppSettings(CustomBaseSettings):
    BASE_API_URL: str = "http://127.0.0.1:8001/api/v1"
    BASE_URL: str = "http://127.0.0.1:8001"
    ENVIRONMENT: str = "local"
    LOGGER_LEVEL: str = "DEBUG"
    OPENAPI_URL: str = "/openapi.json"
    PROJECT_DESCRIPTION: str = "Асинхронный сервис процессинга платежей"
    PROJECT_NAME: str = "Payment Service"
    TIMEZONE: str = "Europe/Moscow"


class RunSettings(CustomBaseSettings):
    RUN_BASE_HOST: str = "127.0.0.1"
    RUN_BASE_PORT: int = 8001
    RELOAD: bool = False


class LoggerSettings(CustomBaseSettings):
    SEND_LOGS: bool = False
    SEND_ERRORS: bool = False
    LOG_DELAY: int = 0.3


class SecuritySettings(CustomBaseSettings):
    API_KEY: str = "dev-api-key"


class RabbitSettings(CustomBaseSettings):
    RABBITMQ_HOST: str = "localhost"
    RABBITMQ_PORT: int = 5672
    RABBITMQ_USER: str = "payment"
    RABBITMQ_PASSWORD: str = "payment"
    RABBITMQ_VHOST: str = "/"
    PAYMENTS_EXCHANGE: str = "payments"
    PAYMENTS_DLX: str = "payments.dlx"
    PAYMENTS_QUEUE: str = "payments.new"
    PAYMENTS_DLQ: str = "payments.new.dlq"
    PAYMENTS_ROUTING_KEY: str = "payments.new"

    @computed_field
    @property
    def RABBITMQ_URL(self) -> str:
        user = quote_plus(self.RABBITMQ_USER)
        password = quote_plus(self.RABBITMQ_PASSWORD)
        vhost = quote(self.RABBITMQ_VHOST, safe="")
        return f"amqp://{user}:{password}@{self.RABBITMQ_HOST}:{self.RABBITMQ_PORT}/{vhost}"


class RetrySettings(CustomBaseSettings):
    RETRY_MAX_ATTEMPTS: int = 3
    RETRY_BASE_DELAY_SECONDS: float = 1.0


class GatewaySettings(CustomBaseSettings):
    GATEWAY_MIN_DELAY_SECONDS: float = 2.0
    GATEWAY_MAX_DELAY_SECONDS: float = 5.0
    GATEWAY_SUCCESS_RATE: float = 0.9


class WebhookSettings(CustomBaseSettings):
    WEBHOOK_TIMEOUT_SECONDS: float = 5.0


class OutboxSettings(CustomBaseSettings):
    OUTBOX_POLL_INTERVAL_SECONDS: float = 1.0


class DatabaseSettings(CustomBaseSettings):
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_DB: str = ""

    @computed_field
    @property
    def DATABASE_URL(self) -> str:
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}"
            f":{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )


class Settings(CustomBaseSettings):
    api: ApiPrefix = ApiPrefix()
    run: RunSettings = RunSettings()
    app: BaseAppSettings = BaseAppSettings()
    log: LoggerSettings = LoggerSettings()
    db: DatabaseSettings = DatabaseSettings()
    security: SecuritySettings = SecuritySettings()
    rabbit: RabbitSettings = RabbitSettings()
    retry: RetrySettings = RetrySettings()
    gateway: GatewaySettings = GatewaySettings()
    webhook: WebhookSettings = WebhookSettings()
    outbox: OutboxSettings = OutboxSettings()


# Files:
LOGS_DIR: Path = BASE_DIR / "logs"

settings = Settings()

# Logger #
log_level: str = settings.app.LOGGER_LEVEL

logger: logging.Logger = make_logger(
    logger_name="monitoring",
    level=log_level,
    base_logger_dir=LOGS_DIR,
)

ModelIDType = uuid.UUID
DB_NAMING_CONVENTION = {
    "all_column_names": lambda constraint, table: "_".join([column.name for column in constraint.columns.values()]),
    "ix": "ix__%(table_name)s__%(all_column_names)s",
    "uq": "uq__%(table_name)s__%(all_column_names)s",
    "ck": "ck__%(table_name)s__%(constraint_name)s",
    "fk": "fk__%(table_name)s__%(all_column_names)s__%(referred_table_name)s",
    "pk": "pk__%(table_name)s",
}

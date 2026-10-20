from typing import Annotated

from fastapi import Security
from fastapi.security import APIKeyHeader

from config import settings
from core.exceptions import UnauthorizedError
from core.security import api_keys_match

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def require_api_key(api_key: Annotated[str | None, Security(api_key_header)]) -> None:
    """Пропускает запрос только с верным статическим ключом."""
    if api_key is None or not api_keys_match(api_key, settings.security.API_KEY):
        raise UnauthorizedError()

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from config import logger
from core.exceptions import BaseAppException


def register_exception_handlers(app: FastAPI) -> None:
    """Подключает обработчики ошибок к конкретному приложению FastAPI."""

    @app.exception_handler(BaseAppException)
    async def handle_app_error(request: Request, exc: BaseAppException) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        logger.error("Unhandled exception: %s", exc, exc_info=True)
        return JSONResponse(status_code=500, content={"detail": "Internal server error"})

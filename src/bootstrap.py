from contextlib import asynccontextmanager

from fastapi import FastAPI

from api.errors import register_exception_handlers
from api.v1.payments import router as payments_router
from config import settings
from on_lifespan import on_shutdown, on_startup
from version import VERSION

PROJECT_NAME = settings.app.PROJECT_NAME
PROJECT_DESCRIPTION = settings.app.PROJECT_DESCRIPTION


def index_page():
    return f"{settings.app.PROJECT_NAME} {settings.app.ENVIRONMENT} v. {VERSION}"


@asynccontextmanager
async def lifespan(app: FastAPI):
    await on_startup()
    yield
    await on_shutdown()


def create_app() -> FastAPI:
    app = FastAPI(
        title=PROJECT_NAME,
        description=PROJECT_DESCRIPTION,
        version=VERSION,
        lifespan=lifespan,
        docs_url="/docs",
        openapi_url="/docs.json",
    )
    register_exception_handlers(app)
    app.add_api_route("/", index_page)
    app.include_router(payments_router, prefix=settings.api.v1.prefix)
    return app

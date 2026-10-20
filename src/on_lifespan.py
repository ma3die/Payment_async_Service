import click

from config import logger, settings

PROJECT_NAME = settings.app.PROJECT_NAME
PROJECT_DESCRIPTION = settings.app.PROJECT_DESCRIPTION


async def on_startup():
    if settings.app.ENVIRONMENT == "local":
        swagger_url = f"http://{settings.run.RUN_BASE_HOST}:{settings.run.RUN_BASE_PORT}/docs"
    else:
        swagger_url = f"{settings.app.BASE_API_URL}/docs"
    message = f"▶️ Backend {PROJECT_NAME} STARTED. Open {swagger_url}"
    color_message = "Open " + click.style(swagger_url, bold=True)
    logger.info(message, extra={"color_message": color_message})


async def on_shutdown():
    message = f"⏹ Backend {PROJECT_NAME} FINISHED."
    logger.info(f"{message=}")

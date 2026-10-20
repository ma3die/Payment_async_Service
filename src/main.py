import uvicorn

from bootstrap import create_app
from config import settings

app = create_app()

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.run.RUN_BASE_HOST,
        port=settings.run.RUN_BASE_PORT,
        reload=settings.run.RELOAD,
    )

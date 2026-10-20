FROM python:3.11-alpine

EXPOSE 8001

RUN mkdir /app

WORKDIR  /app

RUN python -m pip install --upgrade pip

COPY requirements.txt .

RUN python -m pip install -r requirements.txt

COPY src .

CMD ["sh", "-c", "alembic upgrade head && gunicorn main:app --worker-class uvicorn.workers.UvicornWorker --workers 1 --threads 2 --preload --timeout 300 --bind 0.0.0.0:8001"]
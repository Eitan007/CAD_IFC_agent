# BIM assistant API — FastAPI + async Postgres
FROM python:3.11-slim-bookworm

WORKDIR /app

COPY requirements-docker.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements-docker.txt

COPY app ./app

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

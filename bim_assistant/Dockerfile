# BIM assistant API — FastAPI + async Postgres
FROM python:3.11-slim-bookworm

WORKDIR /app

COPY requirements-docker.txt .
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgl1 libx11-6 \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --upgrade pip \
    && pip install -r requirements-docker.txt

COPY app ./app
COPY samples ./samples

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

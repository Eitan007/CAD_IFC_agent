# LiveKit BIM voice worker — connects to LiveKit Cloud and calls the FastAPI BIM API
# Same base as bim_assistant API — reuses cached layers when Docker Hub is slow
FROM python:3.11-slim-bookworm

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements-docker.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements-docker.txt

COPY agent.py .

# Prefetch Silero + turn-detector weights (slow; cached in image layer)
RUN python agent.py download-files

ENV PYTHONUNBUFFERED=1

CMD ["python", "agent.py", "start"]

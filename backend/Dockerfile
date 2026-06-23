# VM 2026 simulation backend - Cloud Run container.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY engine.py model_data.py store.py app.py elo_ratings.json odds_snapshot.json analysis.json ./

# Cloud Run sets $PORT (default 8080). One worker is plenty at minimal traffic;
# the sim is CPU-bound, so concurrency is capped via Cloud Run settings.
ENV PORT=8080
CMD exec uvicorn app:app --host 0.0.0.0 --port ${PORT} --workers 1

# backend/Dockerfile
FROM python:3.11-slim

# === ENV ===
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TZ=UTC

# === Утилиты ===
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
 && rm -rf /var/lib/apt/lists/*

# === Рабочая директория ===
WORKDIR /app

# === Зависимости ===
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# === Исходники ===
COPY . .

# === Non-root user ===
RUN useradd -m appuser
USER appuser

# === Экспонируем порт ===
EXPOSE 8000

# === Gunicorn (параметры переопределяются в docker-compose) ===
ENV GUNICORN_WORKERS=2 \
    GUNICORN_BIND=0.0.0.0:8000 \
    GUNICORN_TIMEOUT=60 \
    GUNICORN_KEEPALIVE=5 \
    GUNICORN_WORKER_CLASS=gthread \
    GUNICORN_WORKER_CONNECTIONS=1000 \
    GUNICORN_LOG_LEVEL=info \
    GUNICORN_THREADS=4

CMD ["gunicorn", "wsgi:app", \
     "-b", "0.0.0.0:8000", \
     "-w", "2", \
     "-k", "gthread", \
     "--threads", "4", \
     "--worker-connections", "1000", \
     "--keep-alive", "5", \
     "--timeout", "60", \
     "--access-logfile", "-", \
     "--log-level", "info"]

# === Healthcheck ===
HEALTHCHECK --interval=10s --timeout=3s --retries=5 \
  CMD curl -sf http://localhost:8000/api/health || exit 1

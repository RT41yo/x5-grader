FROM python:3.11-slim

# Установим зависимости для psycopg2 и healthcheck-скрипта
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    netcat-openbsd \
 && rm -rf /var/lib/apt/lists/*

# Рабочая директория
WORKDIR /app

# Скопируем зависимости
COPY requirements.txt .

# Установим зависимости
RUN pip install --no-cache-dir -r requirements.txt

# Скопируем исходники
COPY . .

# Экспонируем порт
EXPOSE 8000

# По умолчанию будет запускать через gunicorn (см. docker-compose)
CMD ["gunicorn", "wsgi:app", "-b", "0.0.0.0:8000", "-w", "2", "-k", "gevent", "--timeout", "60"]

#!/usr/bin/env bash
# Скрипт ожидания доступности сервисов (Postgres, Langflow и др.)

set -e

host="$1"
port="$2"

echo "⏳ Waiting for $host:$port ..."

while ! nc -z "$host" "$port"; do
  sleep 1
done

echo "✅ $host:$port is available"

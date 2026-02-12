#!/usr/bin/env bash
# Start Postgres + Redis, init DB, then run backend.
set -e
cd "$(dirname "$0")/.."

echo "Starting Postgres and Redis..."
docker-compose up -d db redis 2>/dev/null || true

echo "Waiting for Postgres..."
for i in {1..30}; do
  if docker-compose exec -T db pg_isready -U postgres 2>/dev/null; then
    break
  fi
  sleep 1
done

echo "Initializing database..."
python -m scripts.init_db 2>/dev/null || true

echo "Starting backend on http://localhost:8000"
echo "  API docs: http://localhost:8000/docs"
echo "  Health:   http://localhost:8000/health"
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

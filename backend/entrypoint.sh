#!/bin/sh
set -e

echo "Waiting for postgres..."
while ! nc -z db 5432; do
  sleep 1
done

echo "Postgres is up - running migrations"
alembic upgrade head

echo "Starting application"
exec "$@"
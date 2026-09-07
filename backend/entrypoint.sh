#!/bin/sh
set -e

# Ждём postgres средствами Python, который в образе и так есть.
# Раньше здесь был netcat, ради которого ставился apt-пакет: лишний слой
# сборки, который вдобавок ломается, когда репозитории Debian недоступны.
echo "Waiting for postgres..."
python - <<'PYEOF'
import os, socket, time
from urllib.parse import urlparse

url = urlparse(os.environ["DATABASE_URL"])
host, port = url.hostname or "db", url.port or 5432

for _ in range(60):
    try:
        with socket.create_connection((host, port), timeout=2):
            break
    except OSError:
        time.sleep(1)
else:
    raise SystemExit(f"postgres {host}:{port} не поднялся за 60 секунд")
PYEOF

echo "Postgres is up - running migrations"
alembic upgrade head

echo "Starting application"
exec "$@"

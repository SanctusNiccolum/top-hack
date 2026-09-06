FROM python:3.12-slim

WORKDIR /app

# Билд-контекст — корень репозитория (см. docker-compose.yaml), не backend/,
# чтобы сюда же можно было скопировать пакет telegram_parser.
COPY backend/requirements.txt .

RUN apt-get update && apt-get install -y \
    netcat-openbsd \
    gcc \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir --upgrade -r requirements.txt

COPY backend/ .
COPY backend/app/db/migrations /app/db/migrations

# Парсер живёт в одном образе с api (вызывается как подпроцесс, не
# отдельный контейнер) — см. backend/app/telegram_analysis/runner.py.
COPY telegram_parser/telegram_parser ./telegram_parser

RUN chmod +x /app/entrypoint.sh

ENTRYPOINT ["/app/entrypoint.sh"]

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

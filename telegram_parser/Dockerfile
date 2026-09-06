# Telethon и asyncpg — чистый Python + готовые wheel'ы под linux, поэтому
# лишние system build-deps сверх slim-образа не нужны.
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY telegram_parser ./telegram_parser

# Процесс держит живую Telegram-сессию всё время своей работы — запускать
# его от root нет причины.
RUN useradd --create-home --uid 1000 parser
USER parser

# Вход — JSON на stdin (см. main.py и README), поэтому ENTRYPOINT без
# аргументов по умолчанию: конкретный вызов формирует caller.
ENTRYPOINT ["python", "-m", "telegram_parser.main"]

FROM python:3.12-slim

WORKDIR /app

# Билд-контекст — корень репозитория (см. docker-compose.yaml), не backend/,
# чтобы сюда же можно было скопировать пакет telegram_parser.
COPY backend/requirements.txt .

# Здесь стоял apt-get с netcat и gcc. Убран: gcc не нужен (в
# зависимостях psycopg2-binary, собирать нечего), а ожидание postgres в
# entrypoint.sh переписано на Python. Лишний слой заодно ломал сборку,
# когда репозитории Debian недоступны.
RUN pip install --no-cache-dir --upgrade -r requirements.txt

COPY backend/ .
COPY backend/app/db/migrations /app/db/migrations

# Парсер живёт в одном образе с api (вызывается как подпроцесс, не
# отдельный контейнер) — см. backend/app/telegram_analysis/runner.py.
COPY telegram_parser/telegram_parser ./telegram_parser

# Скоринг по банковской выписке — тоже подпроцессом из этого же образа
# (см. app/statement_scoring/runner.py). Нужны и src/, и обученная модель.
COPY statement_scoring ./statement_scoring

# Срезаем CR перед chmod. На Windows git может выдать файл с CRLF, и тогда
# в shebang попадает \r: ядро ищет интерпретатор "/bin/sh\r", которого нет,
# и контейнер падает с "exec /app/entrypoint.sh: no such file or directory"
# при существующем файле. .gitattributes это лечит только для новых
# чекаутов, а уже лежащие в рабочей копии файлы не трогает — поэтому
# нормализуем здесь, чтобы образ собирался одинаково на любой машине.
RUN sed -i 's/\r$//' /app/entrypoint.sh && chmod +x /app/entrypoint.sh

ENTRYPOINT ["/app/entrypoint.sh"]

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

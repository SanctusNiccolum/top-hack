FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir --upgrade -r requirements.txt

COPY tg_scoring ./tg_scoring

EXPOSE 8000

CMD ["uvicorn", "tg_scoring.api:app", "--host", "0.0.0.0", "--port", "8000"]

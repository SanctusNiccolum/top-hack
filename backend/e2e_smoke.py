# -*- coding: utf-8 -*-
"""Сквозная проверка API: регистрация -> анкета -> выписка -> отчёт.

Запуск (бэкенд должен быть поднят: docker compose up -d):
    python make_test_statement.py   # один раз, создаст test_statement.pdf
    python e2e_smoke.py
"""
import json
import sys
from pathlib import Path
import urllib.request
import uuid

BASE = "http://localhost:8001"
# PDF генерируется рядом: python make_test_statement.py
PDF = str(Path(__file__).resolve().parent / "test_statement.pdf")

token = None


def call(method, path, body=None, files=None):
    url = BASE + path
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    if files:
        boundary = uuid.uuid4().hex
        with open(files, "rb") as fh:
            content = fh.read()
        parts = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="file"; filename="statement.pdf"\r\n'
            f"Content-Type: application/pdf\r\n\r\n"
        ).encode() + content + f"\r\n--{boundary}--\r\n".encode()
        headers["Content-Type"] = f"multipart/form-data; boundary={boundary}"
        data = parts
    elif body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    else:
        data = None

    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read().decode() or "null")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode() or "null")


def step(title, status, payload, expect=200):
    ok = "OK " if status == expect else "!! "
    print(f"{ok}[{status}] {title}")
    if status != expect:
        print("     ответ:", json.dumps(payload, ensure_ascii=False)[:300])
    return status == expect


phone = "+7900" + uuid.uuid4().hex[:7]
ok = True

st, data = call("POST", "/account", {"phone_number": phone, "password": "test12345"})
ok &= step(f"регистрация {phone}", st, data)
token = data["session_token"]
user_id = data["user_id"]

anketa = {
    "first_name": "Антон", "last_name": "Тестов", "age": 21,
    "city": "Екатеринбург", "family_status": "SINGLE",
    "student_status": "FULL_TIME", "student_course": "THIRD",
    "monthly_income": 45000, "self_employed": False,
    "income_frequency": "ONE_TWO_TIMES_MONTH", "income_source": "EMPLOYMENT",
    "credit_history": "BANK_CREDIT", "payment_overdue": "NO",
    "payment_method": "BANK_CARD",
    "subscriptions": ["EDUCATION", "SOFTWARE"],
}
st, data = call("PUT", "/account", anketa)
ok &= step("заполнение анкеты (PUT /account)", st, data)

st, data = call("POST", "/account/complete")
ok &= step("завершение анкеты (POST /account/complete)", st, data)

st, data = call("POST", "/report", {"monthly_payments": 9800,
                                    "npd_certificate_attached": False})
ok &= step("отчёт ТОЛЬКО по анкете", st, data)
survey_only = data
print(f"     score={data.get('score')} survey={data.get('survey_score')} "
      f"statement={data.get('statement_score')}")

st, data = call("POST", "/consent", {"consent_type": "bank_statement",
                                     "document_version": "v1"})
ok &= step("согласие на обработку выписки", st, data, expect=201)

st, data = call("POST", "/statement/upload", files=PDF)
ok &= step("загрузка PDF-выписки", st, data)
statement_score = data.get("statement_score")
print(f"     statement_score={statement_score}")

st, data = call("POST", "/report", {"monthly_payments": 9800,
                                    "npd_certificate_attached": False})
ok &= step("отчёт ПОСЛЕ выписки (склейка двух веток)", st, data)
print(f"     score={data.get('score')} survey={data.get('survey_score')} "
      f"statement={data.get('statement_score')} telegram_delta={data.get('telegram_delta')}")
print(f"     комментарий сохранён: {bool(data.get('comment_from_ai'))}")

# Проверяем саму арифметику склейки: веса 0.4/0.4, telegram отсутствует,
# значит итог = среднее двух веток.
if data.get("survey_score") and data.get("statement_score"):
    s, b = float(data["survey_score"]), float(data["statement_score"])
    expected = round((s * 0.4 + b * 0.4) / 0.8, 2)
    got = float(data["score"])
    match = abs(expected - got) < 0.01
    ok &= match
    print(f"{'OK ' if match else '!! '}арифметика склейки: ожидалось {expected}, получено {got}")

print()
print("ИТОГ:", "всё прошло" if ok else "ЕСТЬ ПРОБЛЕМЫ")
sys.exit(0 if ok else 1)

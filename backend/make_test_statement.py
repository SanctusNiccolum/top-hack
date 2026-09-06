# -*- coding: utf-8 -*-
"""Генерирует тестовую PDF-выписку (нужен reportlab: pip install reportlab) в формате, который ждёт
statement_scoring/src/parser.py (две строки на операцию, суммы с
пробелом-разделителем тысяч и запятой, знак "+" = приход)."""
import random
from datetime import datetime, timedelta
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

pdfmetrics.registerFont(TTFont("Arial", "C:/Windows/Fonts/arial.ttf"))

random.seed(20260907)

START = datetime(2026, 6, 1)
END = datetime(2026, 8, 31)

GROCERY = ["PYATEROCHKA. EKATERINBURG RUS.", "MAGNIT MM. EKB RUS.", "LENTA. EKB RUS."]
TRANSPORT = ["METRO EKB. EKATERINBURG RUS.", "YANDEX GO. MOSCOW RUS."]
CAFE = ["SUSHI MASTER. EKB RUS.", "STOLOVAYA 1. EKB RUS.", "COFFEE LIKE. EKB RUS."]
PHARMACY = ["EAPTEKA. MOSCOW RUS.", "APTEKA OZERKI. EKB RUS."]


def money(value: float) -> str:
    """1234.5 -> '1 234,50' (пробел как разделитель тысяч)."""
    s = f"{abs(value):,.2f}".replace(",", " ").replace(".", ",")
    return s


rows = []          # (dt, time, category, amount, proc_dt, auth, description)
auth = 100000000

day = START
while day <= END:
    # Зарплата дважды в месяц — регулярный доход.
    if day.day in (5, 20):
        auth += 1
        rows.append((day, "09:12", "Зачисление зарплаты", 41500.00,
                     day, str(auth), 'Зачисление зарплаты ООО "ТЕХНОСФЕРА"'))

    # Подработка — нерегулярный приход через СБП.
    if day.day in (11, 27) and random.random() < 0.7:
        auth += 1
        amount = round(random.uniform(4000, 12000), 2)
        rows.append((day, "18:40", "Перевод СБП", amount,
                     day, str(auth), "Перевод от А. Петров"))

    # Аренда — крупный регулярный платёж (прокси долговой нагрузки).
    if day.day == 7:
        auth += 1
        rows.append((day, "12:00", "Перевод СБП", -28000.00,
                     day, str(auth), "Перевод в Сбербанк. Аренда"))

    # Кредитный платёж — регулярная серия.
    if day.day == 15:
        auth += 1
        rows.append((day, "10:30", "Погашение кредита", -9800.00,
                     day, str(auth), 'Погашение кредита ПАО "СБЕРБАНК"'))

    # Ежедневные бытовые траты.
    for _ in range(random.randint(1, 3)):
        auth += 1
        kind = random.random()
        if kind < 0.45:
            cat, desc, lo, hi = "Супермаркеты", random.choice(GROCERY), 250, 2600
        elif kind < 0.65:
            cat, desc, lo, hi = "Транспорт", random.choice(TRANSPORT), 60, 700
        elif kind < 0.85:
            cat, desc, lo, hi = "Рестораны и кафе", random.choice(CAFE), 300, 1800
        else:
            cat, desc, lo, hi = "Здоровье и красота", random.choice(PHARMACY), 200, 2200
        amount = -round(random.uniform(lo, hi), 2)
        hh = random.randint(8, 22)
        mm = random.randint(0, 59)
        proc = day + timedelta(days=random.choice([0, 1]))
        rows.append((day, f"{hh:02d}:{mm:02d}", cat, amount,
                     proc, str(auth), f"{desc} Карта **4321"))

    day += timedelta(days=1)

income = sum(r[3] for r in rows if r[3] > 0)
expense = sum(-r[3] for r in rows if r[3] < 0)

OUT = str(Path(__file__).resolve().parent / "test_statement.pdf")

c = canvas.Canvas(OUT, pagesize=A4)
width, height = A4
y = height - 40


def line(text, size=8):
    global y, c
    if y < 40:
        c.showPage()
        c.setFont("Arial", size)
        y = height - 40
    c.setFont("Arial", size)
    c.drawString(30, y, text)
    y -= 11


line("Индивидуальная выписка по платёжному счёту", 11)
line(f"За период {START.strftime('%d.%m.%Y')} — {END.strftime('%d.%m.%Y')}", 9)
line("Счёт **** 4321", 9)
line(f"Пополнение +{money(income)}", 9)
line(f"Списание {money(expense)}", 9)
line("")

for dt, tm, cat, amount, proc, code, desc in rows:
    sign = "+" if amount > 0 else ""
    line(f"{dt.strftime('%d.%m.%Y')} {tm} {cat} {sign}{money(amount)}")
    line(f"{proc.strftime('%d.%m.%Y')} {code} {desc}")

c.save()
print(f"OK: {OUT}")
print(f"операций: {len(rows)}, доход: {money(income)}, расход: {money(expense)}")

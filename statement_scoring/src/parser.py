# -*- coding: utf-8 -*-
"""
parser.py — извлечение транзакций из PDF-выписки по счёту/карте.

Формат ориентирован на выписки Сбербанка вида
«Индивидуальная выписка по платёжному счёту», но написан достаточно
терпимо к вариациям, чтобы пережить небольшие отличия в вёрстке
(лишние пробелы, неразрывные пробелы, перенос строк).

Каждая операция в исходном PDF занимает ДВЕ строки текста:

    <дата> <время> <категория> <сумма>
    <дата обработки> <код авторизации> <описание операции>

Сумма без знака — списание (расход), сумма со знаком «+» — пополнение
(доход). Это единственный надёжный признак направления операции в
данном формате: категория сама по себе не говорит, приход это или
расход (например, «Перевод СБП» бывает и туда, и оттуда).
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd
import pdfplumber

# Строка-заголовок операции: дата, время, категория, сумма
_HEADER_RE = re.compile(
    r"^(?P<date>\d{2}\.\d{2}\.\d{4})\s+"
    r"(?P<time>\d{2}:\d{2})\s+"
    r"(?P<category>.+?)\s+"
    r"(?P<amount>[+-]?[\d\s\u00a0\u202f]+,\d{2})$"
)

# Строка-детализация операции: дата обработки, код, описание
_DETAIL_RE = re.compile(
    r"^(?P<proc_date>\d{2}\.\d{2}\.\d{4})\s+"
    r"(?P<auth_code>\d+)\s+"
    r"(?P<description>.+)$"
)

# Заголовок счёта, из которого можно достать заявленные банком итоги —
# используется как контрольная сумма после парсинга.
_TOTALS_RE = {
    "income": re.compile(r"Пополнение\s+\+?([\d\s\u00a0\u202f]+,\d{2})"),
    "expense": re.compile(r"Списание\s+([\d\s\u00a0\u202f]+,\d{2})"),
}

_PERIOD_RE = re.compile(
    r"За период\s+(\d{2}\.\d{2}\.\d{4})\s*[—-]\s*(\d{2}\.\d{2}\.\d{4})"
)

_CARD_TAIL_RE = re.compile(r"\*{2,4}(\d{4})")


def _clean_amount(raw: str) -> float:
    """'−|+ 1 234,56' (в т.ч. с разными видами пробелов) -> float со знаком."""
    s = raw.strip()
    sign = -1.0
    if s.startswith("+"):
        sign = 1.0
        s = s[1:]
    elif s.startswith("-"):
        s = s[1:]
    s = unicodedata.normalize("NFKC", s)
    s = s.replace(" ", "").replace("\u00a0", "").replace("\u202f", "")
    s = s.replace(",", ".")
    return sign * float(s)


def _extract_counterparty(description: str) -> Optional[str]:
    """
    Грубое выделение контрагента/получателя из свободного текста описания,
    достаточное для группировки повторяющихся платежей (см. features.py:
    поиск регулярных платежей = прокси текущей кредитной нагрузки).
    """
    d = description

    m = re.search(r"Перевод (?:в|из)\s+([A-ЯA-Zа-яa-z\-\.]+)", d)
    if m:
        return m.group(1).strip(" .")

    m = re.search(r'(АО|ООО|ПАО)\s+"([^"]+)"', d)
    if m:
        return m.group(2).strip()

    m = re.search(r"Перевод (?:от|в)\s+([А-ЯЁ]\.\s?[А-ЯЁ][а-яё]+(?:\s[А-ЯЁ][а-яё]+)?)", d)
    if m:
        return m.group(1).strip()

    # Мерчант вида "EAPTEKA. MOSCOW RUS." — берём первое слово до точки/цифры
    m = re.match(r"^([A-Z][A-Z0-9_]{2,})", d)
    if m:
        return m.group(1).strip()

    return description.split(".")[0].strip()[:40]


@dataclass
class Transaction:
    date: datetime
    time: str
    category: str
    amount: float           # со знаком: >0 доход, <0 расход
    direction: str          # "in" | "out"
    processing_date: datetime
    auth_code: str
    description: str
    counterparty: Optional[str]
    card_or_account: Optional[str]


def _iter_transaction_lines(lines: list[str]):
    i = 0
    n = len(lines)
    while i < n:
        h = _HEADER_RE.match(lines[i].strip())
        if h and i + 1 < n:
            d = _DETAIL_RE.match(lines[i + 1].strip())
            if d:
                yield h, d
                i += 2
                continue
        i += 1


def parse_statement(pdf_path: str | Path) -> pd.DataFrame:
    """
    Парсит PDF-выписку и возвращает DataFrame с одной строкой на операцию.

    Колонки:
        date, time, category, amount, direction, processing_date,
        auth_code, description, counterparty, card_or_account
    """
    pdf_path = Path(pdf_path)
    with pdfplumber.open(pdf_path) as pdf:
        full_text = "\n".join(page.extract_text() or "" for page in pdf.pages)

    lines = full_text.split("\n")

    transactions: list[Transaction] = []
    for h, d in _iter_transaction_lines(lines):
        amount = _clean_amount(h.group("amount"))
        description = d.group("description").strip()
        card_match = _CARD_TAIL_RE.search(description)
        transactions.append(
            Transaction(
                date=datetime.strptime(h.group("date"), "%d.%m.%Y"),
                time=h.group("time"),
                category=h.group("category").strip(),
                amount=amount,
                direction="in" if amount > 0 else "out",
                processing_date=datetime.strptime(d.group("proc_date"), "%d.%m.%Y"),
                auth_code=d.group("auth_code"),
                description=description,
                counterparty=_extract_counterparty(description),
                card_or_account=card_match.group(1) if card_match else None,
            )
        )

    if not transactions:
        raise ValueError(
            "Не удалось извлечь ни одной операции. Проверьте, что PDF содержит "
            "текстовый слой (не скан) и соответствует ожидаемому формату выписки."
        )

    df = pd.DataFrame([asdict(t) for t in transactions])
    df = df.sort_values("date").reset_index(drop=True)

    period = _PERIOD_RE.search(full_text)
    df.attrs["period_start"] = (
        datetime.strptime(period.group(1), "%d.%m.%Y") if period else df["date"].min()
    )
    df.attrs["period_end"] = (
        datetime.strptime(period.group(2), "%d.%m.%Y") if period else df["date"].max()
    )

    for key, rx in _TOTALS_RE.items():
        m = rx.search(full_text)
        # Итоговые суммы в шапке — это магнитуды («Списание 439 923,86» без
        # знака минус означает «списано 439 923,86», а не отрицательное
        # число), поэтому здесь берём модуль, в отличие от сумм по операциям.
        df.attrs[f"declared_{key}"] = abs(_clean_amount(m.group(1))) if m else None

    return df


def validate_against_declared_totals(df: pd.DataFrame, tol: float = 1.0) -> dict:
    """
    Сверяет сумму распарсенных операций с итогами, которые банк печатает
    в шапке выписки («Пополнение» / «Списание»). Полезно как self-check:
    если суммы не сходятся — где-то не распарсилась операция (например,
    перенос строки внутри длинного описания).
    """
    parsed_income = df.loc[df.amount > 0, "amount"].sum()
    parsed_expense = -df.loc[df.amount < 0, "amount"].sum()
    declared_income = df.attrs.get("declared_income")
    declared_expense = df.attrs.get("declared_expense")

    result = {
        "parsed_income": round(parsed_income, 2),
        "declared_income": declared_income,
        "income_match": (
            declared_income is not None and abs(parsed_income - declared_income) <= tol
        ),
        "parsed_expense": round(parsed_expense, 2),
        "declared_expense": declared_expense,
        "expense_match": (
            declared_expense is not None and abs(parsed_expense - declared_expense) <= tol
        ),
    }
    return result


if __name__ == "__main__":
    import sys

    path = sys.argv[1] if len(sys.argv) > 1 else None
    if not path:
        print("Использование: python parser.py <путь_к_выписке.pdf>")
        raise SystemExit(1)

    df = parse_statement(path)
    print(df.to_string())
    print()
    print("Проверка контрольных сумм:", validate_against_declared_totals(df))

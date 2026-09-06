"""
Таксономия категорий, веса и запрещённый список.

Единственный источник правды по категориям. Промпт для LLM собирается
из этого же файла (см. prompts.py), поэтому рассинхрона между тем, что
модель умеет возвращать, и тем, что умеет считать агрегатор, быть не может.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Polarity(str, Enum):
    POSITIVE = "positive"
    NEGATIVE = "negative"


@dataclass(frozen=True)
class Category:
    key: str
    polarity: Polarity
    weight: float          # максимальный вклад в дельту при полном насыщении
    title_ru: str          # для объяснения пользователю
    definition: str        # уходит в промпт
    hard_risk: bool = False  # участвует в расчёте risk_level


CATEGORIES: tuple[Category, ...] = (
    # ---------------- позитивные ----------------
    Category(
        key="employment_stable",
        polarity=Polarity.POSITIVE,
        weight=8.0,
        title_ru="стабильная занятость",
        definition="есть работа: вышел/работаю/оффер/коллеги/руководитель/рабочие задачи как рутина",
    ),
    Category(
        key="obligation_fulfilled",
        polarity=Polarity.POSITIVE,
        weight=7.0,
        title_ru="исполнение обязательств",
        definition="закрыл кредит, погасил долг, внёс платёж вовремя, вернул занятое",
    ),
    Category(
        key="income_regular",
        polarity=Polarity.POSITIVE,
        weight=6.0,
        title_ru="регулярный доход",
        definition="пришла зарплата, оплата от клиента, регулярное поступление средств",
    ),
    Category(
        key="financial_planning",
        polarity=Polarity.POSITIVE,
        weight=6.0,
        title_ru="финансовое планирование",
        definition="коплю, откладываю, подушка безопасности, веду бюджет, долгосрочные инвестиции без плеча",
    ),
    Category(
        key="business_activity",
        polarity=Polarity.POSITIVE,
        weight=5.0,
        title_ru="деловая активность",
        definition="свои клиенты и заказы, самозанятость, проект приносит деньги",
    ),
    Category(
        key="education_active",
        polarity=Polarity.POSITIVE,
        weight=4.0,
        title_ru="активная учёба",
        definition="учусь, сессия, диплом, профильные курсы и повышение квалификации",
    ),
    Category(
        key="long_horizon_planning",
        polarity=Polarity.POSITIVE,
        weight=4.0,
        title_ru="долгосрочные планы",
        definition="планы на год и дальше, ипотека, переезд по работе, подготовленная крупная покупка",
    ),
    # ---------------- негативные ----------------
    Category(
        key="gambling",
        polarity=Polarity.NEGATIVE,
        weight=-12.0,
        title_ru="азартные игры и ставки",
        definition="ставки, букмекеры, казино, слоты, лотереи, «поднял/слил» в игровом контексте",
        hard_risk=True,
    ),
    Category(
        key="debt_distress",
        polarity=Polarity.NEGATIVE,
        weight=-10.0,
        title_ru="долговые проблемы",
        definition="нечем платить, просрочка, коллекторы, перекредитовка, долги растут",
        hard_risk=True,
    ),
    Category(
        key="microloan_reliance",
        polarity=Polarity.NEGATIVE,
        weight=-8.0,
        title_ru="микрозаймы",
        definition="МФО, займ до зарплаты, ломбард как регулярная практика",
        hard_risk=True,
    ),
    Category(
        key="income_instability",
        polarity=Polarity.NEGATIVE,
        weight=-6.0,
        title_ru="нестабильный доход",
        definition="не платят, кинули с оплатой, нет заказов второй месяц, доход просел",
    ),
    Category(
        key="job_loss",
        polarity=Polarity.NEGATIVE,
        weight=-5.0,
        title_ru="потеря работы",
        definition="уволили, сократили, ушёл без нового места, ищу работу",
    ),
    Category(
        key="impulsive_spending",
        polarity=Polarity.NEGATIVE,
        weight=-4.0,
        title_ru="импульсивные траты",
        definition="спустил зарплату, «опять ничего не осталось», крупная спонтанная покупка в кредит",
    ),
    Category(
        key="high_risk_speculation",
        polarity=Polarity.NEGATIVE,
        weight=-4.0,
        title_ru="высокорисковые спекуляции",
        definition="торговля с плечом, памп-группы, обещания кратной доходности, финансовые пирамиды",
    ),
)

BY_KEY: dict[str, Category] = {c.key: c for c in CATEGORIES}
CATEGORY_KEYS: frozenset[str] = frozenset(BY_KEY)
HARD_RISK_KEYS: frozenset[str] = frozenset(c.key for c in CATEGORIES if c.hard_risk)


# Запрещённые темы. Модель обязана не создавать по ним сигналов; всё, что
# всё-таки просочилось в ответ, отсекается валидатором.
#
# Основание — не осторожность, а 152-ФЗ: раса, национальность, политические
# взгляды, религиозные убеждения, состояние здоровья, интимная жизнь и
# судимость отнесены к специальным категориям персональных данных, для
# обработки которых согласия на парсинг канала недостаточно.
DENIED_TOPICS: tuple[str, ...] = (
    "здоровье, диагнозы, лечение, лекарства, психическое состояние, инвалидность",
    "религиозные убеждения и практики",
    "национальность, раса, этническое происхождение",
    "политические взгляды, участие в акциях",
    "сексуальная ориентация и личная жизнь",
    "семейное положение, дети, беременность",
    "судимость, приводы, участие в конфликтах",
    "членство в профсоюзах и общественных объединениях",
)

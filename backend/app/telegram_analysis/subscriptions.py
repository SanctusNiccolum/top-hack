"""Поправка к скору по подпискам на каналы.

Третий сигнал из формулировки кейса («лексика, частота упоминания работы,
подписки на финансовые каналы»). Первые два даёт LLM по текстам
сообщений, этот — считается здесь, детерминированно.

Почему отдельно от LLM: подписка это факт, а не высказывание. Её не надо
интерпретировать — достаточно сверить @username канала со справочником
`trusted_channels`. Гонять такое через модель значило бы платить за
токены и получать недетерминированный ответ там, где хватает JOIN'а.

Сверка идёт по username, а не по названию: заголовок канала владелец
меняет как угодно, а username привязан к каналу.
"""
from __future__ import annotations

import math
from decimal import Decimal

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# Максимальный вклад категории при полном насыщении.
CATEGORY_WEIGHTS = {
    "finance": 2.0,
    "job": 1.5,
    "education": 1.5,
    "crypto": -1.5,
    "microloan": -3.0,
    "gambling": -4.0,
}

CATEGORY_TITLES = {
    "finance": "подписки на финансовые каналы",
    "job": "подписки на каналы о работе",
    "education": "образовательные каналы",
    "crypto": "криптоканалы",
    "microloan": "каналы микрозаймов",
    "gambling": "каналы ставок и азартных игр",
}

# Насыщение — та же формула, что в tg-ai: без неё двадцать финансовых
# каналов давали бы +40, и подписки перевесили бы весь остальной анализ.
SATURATION_K = 3.0

# Подписки — вспомогательный сигнал: это лишь косвенный признак, человек
# мог подписаться на канал из любопытства. Ограничиваем их влияние, чтобы
# они не перебивали то, что человек пишет сам.
DELTA_LIMIT = Decimal("10")


async def subscription_delta(
    db: AsyncSession,
    telegram_user_id: int,
) -> tuple[Decimal, list[dict]]:
    """Возвращает (поправка, разбивка по категориям).

    Разбивка — в том же формате, что факторы от tg-ai
    ({category, contribution, evidence_count}), чтобы фронт показывал их
    одним списком и не различал источник.
    """
    rows = (
        await db.execute(
            text(
                "SELECT tc.category, count(*) AS matched "
                "FROM subscriptions s "
                "JOIN trusted_channels tc "
                "  ON tc.trusted_channel_id = s.trusted_channel_id "
                "WHERE s.user_id = :tg_id "
                "GROUP BY tc.category"
            ),
            {"tg_id": telegram_user_id},
        )
    ).all()

    factors: list[dict] = []
    total = 0.0

    for row in rows:
        weight = CATEGORY_WEIGHTS.get(row.category)
        if weight is None:
            # Категория есть в справочнике, но веса для неё не задали —
            # молча игнорируем, а не считаем нулём наугад.
            continue

        saturation = 1 - math.exp(-row.matched / SATURATION_K)
        contribution = weight * saturation
        total += contribution

        factors.append(
            {
                "category": f"subscription_{row.category}",
                "title_ru": CATEGORY_TITLES.get(row.category, row.category),
                "contribution": round(contribution, 2),
                "evidence_count": int(row.matched),
            }
        )

    delta = Decimal(str(round(total, 2)))
    delta = max(-DELTA_LIMIT, min(DELTA_LIMIT, delta))

    return delta, factors

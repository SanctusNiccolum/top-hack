"""
Двухступенчатый пре-фильтр (§7 спеки).

Отправлять в LLM все 640 сообщений не нужно и вредно: это в 5-6 раз
дороже и точность ниже — чем больше нейтрального шума в чанке, тем чаще
модель выдумывает сигнал, лишь бы не вернуть пустой ответ.

Ступень 0 (здесь): словарь маркеров + контрольная случайная выборка.
Ступень 1: LLM размечает только то, что прошло.

Контрольная выборка — не про полноту, а про измеримость. Сигналы, которые
LLM находит в этих 10%, — это прямая оценка recall словаря маркеров.
Если модель регулярно находит там то, чего словарь не поймал, словарь надо
расширять; если почти ничего — фильтр можно ужесточить.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Protocol

from .markers import find_marker_categories
from .schemas import InputMessage


@dataclass
class PrefilterResult:
    selected: list[InputMessage]
    total: int
    by_marker: int = 0
    by_control: int = 0
    by_vector: int = 0
    marker_hits: dict[str, int] = field(default_factory=dict)

    @property
    def skipped(self) -> int:
        return self.total - len(self.selected)

    @property
    def control_ids(self) -> set[str]:
        """id сообщений, попавших только по контрольной выборке. По ним
        считается recall словаря — см. cli.py prefilter-report."""
        return self._control_ids

    _control_ids: set[str] = field(default_factory=set)


class VectorPrefilter(Protocol):
    """Точка расширения для семантического слоя (v2).

    Объединение с лексикой делается через OR, а не AND: фильтр
    recall-ориентированный, и объединение может только улучшить полноту.
    """

    def select(self, messages: list[InputMessage], top_n: int) -> set[str]:
        """Возвращает id сообщений, семантически близких к прототипам."""
        ...


def run_prefilter(
    messages: list[InputMessage],
    control_ratio: float = 0.10,
    seed: int = 42,
    vector_filter: VectorPrefilter | None = None,
    vector_top_n: int = 50,
) -> PrefilterResult:
    result = PrefilterResult(selected=[], total=len(messages))

    passed_marker: set[str] = set()
    rest: list[InputMessage] = []

    for msg in messages:
        cats = find_marker_categories(msg.text)
        if cats:
            passed_marker.add(msg.id)
            for c in cats:
                result.marker_hits[c] = result.marker_hits.get(c, 0) + 1
        else:
            rest.append(msg)

    passed_vector: set[str] = set()
    if vector_filter is not None and rest:
        passed_vector = vector_filter.select(rest, vector_top_n) - passed_marker

    # контрольная выборка берётся из того, что не прошло ни один фильтр —
    # только тогда она честно измеряет полноту словаря
    remaining = [m for m in rest if m.id not in passed_vector]
    control_n = int(round(len(remaining) * control_ratio))
    rng = random.Random(seed)  # фиксированный seed: воспроизводимость прогонов
    control_ids = {m.id for m in rng.sample(remaining, control_n)} if control_n else set()

    selected_ids = passed_marker | passed_vector | control_ids
    result.selected = [m for m in messages if m.id in selected_ids]
    result.by_marker = len(passed_marker)
    result.by_vector = len(passed_vector)
    result.by_control = len(control_ids)
    result._control_ids = control_ids
    return result


# ------------------------------------------------------------------
#  Семантический слой (по умолчанию выключен)
# ------------------------------------------------------------------

# Прототипы — реальные фразы, а не названия категорий: эмбеддинг слова
# "gambling" и эмбеддинг "слил зарплату на ставках" живут в разных местах
# пространства.
PROTOTYPES: dict[str, list[str]] = {
    "employment_stable": [
        "вышел на новую работу, оффер подписал",
        "начальник попросил задержаться до конца квартала",
        "сегодня был тяжёлый рабочий день, много задач",
    ],
    "obligation_fulfilled": [
        "внёс последний платёж по кредиту",
        "наконец рассчитался по всем долгам",
    ],
    "income_regular": [
        "пришла зарплата, наконец-то",
        "клиент перевёл оплату за месяц",
    ],
    "financial_planning": [
        "откладываю каждый месяц на подушку безопасности",
        "начал вести бюджет и считать расходы",
    ],
    "business_activity": [
        "взял нового клиента на проект",
        "выставил счёт заказчику за работу",
    ],
    "education_active": [
        "готовлюсь к сессии, сдаю экзамены",
        "закончил курс и получил сертификат",
    ],
    "long_horizon_planning": [
        "копим на первоначальный взнос по ипотеке",
        "через год планируем переезд",
    ],
    "gambling": [
        "опять в минусе после выходных, не заходят экспрессы",
        "поставил на матч и всё проиграл",
        "закинул депозит и прокрутил его в автоматах",
    ],
    "debt_distress": [
        "нечем платить по кредиту в этом месяце",
        "снова звонят и требуют вернуть деньги",
    ],
    "microloan_reliance": [
        "взял до зарплаты под конский процент",
        "опять пришлось занимать в микрофинансовой",
    ],
    "income_instability": [
        "заказчик пропал и не заплатил за работу",
        "второй месяц нет заказов совсем",
    ],
    "job_loss": [
        "попросили освободить стол до пятницы",
        "остался без работы, рассылаю резюме",
    ],
    "impulsive_spending": [
        "получил деньги и за два дня всё спустил",
        "опять к концу месяца пусто на карте",
    ],
    "high_risk_speculation": [
        "зашёл с плечом, надеюсь на иксы",
        "закинул в проект с обещанной доходностью 40% в месяц",
    ],
}

DEFAULT_EMBEDDING_MODEL = "intfloat/multilingual-e5-base"


class SentenceTransformerPrefilter:
    """Референсная реализация VectorPrefilter.

    Не подключена по умолчанию: тянет ~500 МБ весов и добавляет
    компонент, чей отсев трудно объяснить («косинус 0.31 при пороге
    0.35» — плохой ответ на вопрос, почему сообщение не проанализировали).
    Включается флагом PREFILTER_USE_VECTORS=true, когда появится золотая
    выборка, на которой можно измерить пользу и откалибровать порог.

    Векторная БД здесь не нужна: 640 сообщений на 768 измерений — это одно
    перемножение матриц, миллисекунды.
    """

    def __init__(
        self,
        model_name: str = DEFAULT_EMBEDDING_MODEL,
        threshold: float = 0.80,
        query_prefix: str = "query: ",
        passage_prefix: str = "passage: ",
    ):
        try:
            from sentence_transformers import SentenceTransformer  # type: ignore
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "PREFILTER_USE_VECTORS=true, но sentence-transformers не установлен. "
                "Поставь: pip install sentence-transformers"
            ) from exc

        self.model = SentenceTransformer(model_name)
        self.threshold = threshold
        self.passage_prefix = passage_prefix

        flat = [(cat, p) for cat, ps in PROTOTYPES.items() for p in ps]
        self._proto_labels = [c for c, _ in flat]
        self._proto_vecs = self.model.encode(
            [query_prefix + p for _, p in flat],
            normalize_embeddings=True,
            show_progress_bar=False,
        )

    def select(self, messages: list[InputMessage], top_n: int) -> set[str]:
        if not messages:
            return set()
        import numpy as np  # локальный импорт: numpy нужен только здесь

        vecs = self.model.encode(
            [self.passage_prefix + m.text for m in messages],
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        # max-similarity к прототипам категории, не к усреднённому центроиду:
        # центроид размывает широкие категории вроде financial_planning
        sims = np.asarray(vecs) @ np.asarray(self._proto_vecs).T
        best = sims.max(axis=1)

        order = best.argsort()[::-1][:top_n]
        return {messages[int(i)].id for i in order if best[int(i)] >= self.threshold}


def build_vector_filter(enabled: bool) -> VectorPrefilter | None:
    return SentenceTransformerPrefilter() if enabled else None

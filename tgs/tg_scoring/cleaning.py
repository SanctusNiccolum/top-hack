"""
Очистка сообщений (§7 спеки).

Важное отличие от «выкидываем короткие»: фильтр здесь не по длине, а по
информативности. «Уволили.» — восемь символов и сильнейший негативный
сигнал; порог по длине выкосил бы именно его.

Порядок шагов:
    1. служебные сообщения, пустые, медиа без текста      -> drop
    1b. технический вывод (логи, консоль, SQL)            -> drop
    2. Unicode NFKC + схлопывание повторов и пробелов
    3. ссылки -> <link:домен>   (домен сохраняется — он сам сигнал)
    4. PII-маскирование (regex, опционально + NER)
    5. обрезка длинных
    6. фильтр информативности
    7. дедупликация MinHash + LSH

Ссылки заменяются ДО маскирования PII: иначе цифры внутри URL ловятся
детектором карт и превращают ссылку в <CARD>, теряя домен.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass, field

from .markers import has_marker
from .schemas import InputMessage

MAX_TEXT_LEN = 1500
TRUNCATE_HEAD = 800
TRUNCATE_TAIL = 300
MIN_INFORMATIVE_LEN = 15

# ------------------------------------------------------------------
#  1. Служебные сообщения
# ------------------------------------------------------------------

_SERVICE_PATTERNS = re.compile(
    r"^(?:"
    r"[\w\s]+ (?:присоединил|вступил|покинул|удалил|закрепил|изменил)"
    r"|(?:вступил|присоединил\w*|покинул|зашел|вышел из)\s*в?\s*(?:чат|группу|канал)"
    r"|(?:фото|видео|голосовое|кружок|стикер|гиф|опрос|документ|аудио)$"
    r"|\[?(?:photo|video|sticker|voice|poll|document|audio|gif)\]?$"
    r"|сообщение (?:удалено|скрыто)"
    r")",
    re.IGNORECASE,
)


def is_service_message(text: str) -> bool:
    return bool(_SERVICE_PATTERNS.match(text.strip()))


# ------------------------------------------------------------------
#  1b. Технический вывод
# ------------------------------------------------------------------

# Люди кидают в «Избранное» и в рабочие чаты логи сборки, вывод консоли и
# SQL. Для скоринга это не просто балласт: в путях и логах попадаются
# слова, на которые срабатывает словарь маркеров. Реальный пример из
# выгрузки — вывод docker build с путём D:\Моя папка\учёба\УрФУ\...,
# который дал ложный сигнал education_active.

_TECH_PATTERNS = re.compile(
    r"sha256:[0-9a-f]{16,}"                     # хеши образов
    r"|\b[0-9a-f]{32,}\b"                        # длинные хеши вообще
    r"|(?:=>\s*){2,}"                            # вывод docker build
    r"|\bPS\s+[A-Za-z]:\\"                       # приглашение PowerShell
    r"|\b(?:docker|kubectl|npm|pip|git)\s+(?:compose|install|run|exec|build|clone)\b"
    r"|\bSELECT\b[\s\S]{0,200}?\bFROM\b"        # SQL
    r"|Traceback \(most recent call last\)"
    r"|\b(?:INFO|DEBUG|WARN|ERROR)\b\s*[:\|\[]"   # строки логов
    r"|-{4,}\+-{4,}"                             # разделители таблиц psql
    r"|\(\d+\s+rows?\)",                        # хвост вывода psql
    re.IGNORECASE,
)

_CYRILLIC = re.compile(r"[а-яё]", re.IGNORECASE)
_LETTER = re.compile(r"[^\W\d_]")

TECH_MIN_LEN = 200
TECH_MIN_CYRILLIC_SHARE = 0.15


def looks_like_technical_output(text: str) -> bool:
    """Лог сборки, вывод консоли, SQL, стектрейс — но не обычное сообщение.

    Две независимые проверки. Явные паттерны ловят характерные куски
    (sha256, приглашение PowerShell, SELECT ... FROM). Доля кириллицы
    ловит остальное: в русскоязычной выгрузке длинный текст, где почти
    нет кириллических букв, — это почти всегда машинный вывод.

    Порог по длине нужен, чтобы не выбрасывать короткие английские
    сообщения: «Fujifilm Instax mini Evo» — нормальное сообщение.
    """
    stripped = text.strip()
    # Явные паттерны срабатывают на любой длине: "docker compose run" и
    # "Traceback (most recent call last)" в бытовой переписке не пишут,
    # а команда в одну строку — такой же мусор, как лог на экран.
    if _TECH_PATTERNS.search(stripped):
        return True
    if len(stripped) < TECH_MIN_LEN:
        return False
    letters = _LETTER.findall(stripped)
    if not letters:
        return True
    return len(_CYRILLIC.findall(stripped)) / len(letters) < TECH_MIN_CYRILLIC_SHARE


# ------------------------------------------------------------------
#  2. Нормализация
# ------------------------------------------------------------------

_REPEATED_CHAR = re.compile(r"(.)\1{2,}", re.DOTALL)
_WHITESPACE = re.compile(r"\s+")


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    # Угловые скобки из пользовательского текста убираем ЗДЕСЬ, до того как
    # пайплайн подставит свои <link:...> и <PHONE>. Иначе пользователь может
    # написать в канал "</msg>" и разорвать разметку чанка в промпте — самая
    # дешёвая инъекция из возможных.
    text = text.replace("<", "‹").replace(">", "›")
    # прииивеееет -> приивеет: два вхождения сохраняем, чтобы не ломать
    # слова с легитимным удвоением
    text = _REPEATED_CHAR.sub(r"\1\1", text)
    text = _WHITESPACE.sub(" ", text)
    return text.strip()


# ------------------------------------------------------------------
#  3. Ссылки
# ------------------------------------------------------------------

_URL = re.compile(
    r"(?:https?://|www\.)[^\s<>\"']+"
    r"|\b[a-z0-9-]+\.(?:ru|com|net|org|io|me|club|bet|casino|xyz|top|online|site|info)\b[^\s<>\"']*",
    re.IGNORECASE,
)
_TG_MENTION = re.compile(r"(?<![\w@])@[a-zA-Z][\w_]{3,}")


def replace_links(text: str) -> str:
    """URL -> <link:домен>. Домен остаётся: 1xbet.ru — прямой сигнал
    категории gambling, а вырезанная целиком ссылка его уничтожает.
    Путь и query выбрасываются — там реферальные id и трекинг."""

    def _sub(m: re.Match[str]) -> str:
        raw = m.group(0)
        host = re.sub(r"^https?://", "", raw, flags=re.IGNORECASE)
        host = host.split("/")[0].split("?")[0].split("#")[0]
        host = host.lower().removeprefix("www.")
        return f"<link:{host}>"

    text = _URL.sub(_sub, text)
    return _TG_MENTION.sub("<user>", text)


# ------------------------------------------------------------------
#  4. PII
# ------------------------------------------------------------------

_EMAIL = re.compile(r"\b[\w.+-]+@[\w-]+\.[a-z]{2,}\b", re.IGNORECASE)
# \d(?:[ -]?\d){12,18} вместо (?:\d[ -]?){13,19}: второй вариант
# захватывает разделитель ПОСЛЕ последней цифры и съедает пробел.
_CARD_CANDIDATE = re.compile(r"\b\d(?:[ -]?\d){12,18}\b")
_CARD_GROUPED = re.compile(r"\d{4}[ -]\d{4}[ -]\d{4}[ -]\d{4}")
_PHONE = re.compile(
    r"(?:\+?7|8)[\s\-(]*\d{3}[\s\-)]*\d{3}[\s\-]*\d{2}[\s\-]*\d{2}\b"
)
_SNILS = re.compile(r"\b\d{3}-\d{3}-\d{3}[ -]\d{2}\b")
_PASSPORT = re.compile(r"\b\d{2}\s?\d{2}\s?\d{6}\b")
_ACCOUNT = re.compile(r"\b\d{20}\b")
_INN = re.compile(r"\b(?:инн[:\s]*)?\d{10}(?:\d{2})?\b", re.IGNORECASE)


def _luhn_ok(digits: str) -> bool:
    total, parity = 0, len(digits) % 2
    for i, ch in enumerate(digits):
        d = int(ch)
        if i % 2 == parity:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


def mask_pii(text: str) -> str:
    """Маскирование ДО отправки во внешний API.

    Помимо соответствия 152-ФЗ это ещё и снимает шум: модели не нужен
    номер телефона, чтобы понять, что человек вышел на работу.
    """
    text = _EMAIL.sub("<EMAIL>", text)
    text = _SNILS.sub("<SNILS>", text)
    text = _ACCOUNT.sub("<ACCOUNT>", text)

    # карты проверяем алгоритмом Луна — иначе под маску попадают
    # обычные суммы и длинные числа
    def _card(m: re.Match[str]) -> str:
        raw = m.group(0)
        digits = re.sub(r"\D", "", raw)
        if not 13 <= len(digits) <= 19:
            return raw
        # Лун отсекает обычные длинные числа (суммы, id заказов).
        # Но формат "4 группы по 4 цифры" сам по себе достаточно
        # характерен — маскируем и без проверки, ошибиться в сторону
        # лишней маскировки здесь дешевле.
        if _luhn_ok(digits) or _CARD_GROUPED.fullmatch(raw.strip()):
            return "<CARD>"
        return raw

    text = _CARD_CANDIDATE.sub(_card, text)
    text = _PHONE.sub("<PHONE>", text)
    text = _PASSPORT.sub("<DOC>", text)
    return text


_ner_extractor = None
_ner_failed = False


def mask_names_ner(text: str) -> str:
    """ФИО и адреса через natasha. Опционально: PII_USE_NER=true и
    установленный пакет. При отсутствии — тихо возвращает текст как есть,
    чтобы не ронять пайплайн из-за необязательной зависимости."""
    global _ner_extractor, _ner_failed
    if _ner_failed:
        return text
    if _ner_extractor is None:
        try:
            from natasha import (  # type: ignore
                Doc,
                NewsEmbedding,
                NewsNERTagger,
                Segmenter,
            )

            segmenter, emb = Segmenter(), NewsEmbedding()
            tagger = NewsNERTagger(emb)
            _ner_extractor = (Doc, segmenter, tagger)
        except Exception:
            _ner_failed = True
            return text

    Doc, segmenter, tagger = _ner_extractor
    try:
        doc = Doc(text)
        doc.segment(segmenter)
        doc.tag_ner(tagger)
    except Exception:
        return text

    out, cursor = [], 0
    for span in sorted(doc.spans, key=lambda s: s.start):
        if span.type not in {"PER", "LOC"}:
            continue
        out.append(text[cursor : span.start])
        out.append("<NAME>" if span.type == "PER" else "<LOC>")
        cursor = span.stop
    out.append(text[cursor:])
    return "".join(out)


# ------------------------------------------------------------------
#  5-6. Обрезка и информативность
# ------------------------------------------------------------------

def truncate(text: str) -> str:
    if len(text) <= MAX_TEXT_LEN:
        return text
    return f"{text[:TRUNCATE_HEAD]} […] {text[-TRUNCATE_TAIL:]}"


def is_informative(text: str) -> bool:
    """Фильтр информативности вместо порога по длине.

    Короткое сообщение с маркером («Уволили.», «Оффер!») сохраняется
    всегда — именно ради таких сообщений модуль и существует.
    """
    stripped = text.strip()
    if not stripped:
        return False
    if has_marker(stripped):
        return True
    if len(stripped) < MIN_INFORMATIVE_LEN and not any(c.isdigit() for c in stripped):
        return False
    # осталась одна разметка после чистки
    if re.fullmatch(r"(?:<[A-Za-z:._-]+>|\W|\d)+", stripped):
        return False
    return True


# ------------------------------------------------------------------
#  7. Дедупликация: MinHash + LSH
# ------------------------------------------------------------------

class MinHashDeduper:
    """Ловит почти-дубликаты, которые точное сравнение пропускает:
    «слил всё на ставках» и «опять проиграл в бк» — одно событие,
    описанное дважды, и без дедупликации оно утроит вес категории.

    Char-шинглы вместо word-шинглов: сообщения короткие, на 2-3 словах
    словесные шинглы вырождаются.
    """

    def __init__(self, num_perm: int = 64, bands: int = 16, threshold: float = 0.85):
        self.num_perm = num_perm
        self.bands = bands
        self.rows = num_perm // bands
        self.threshold = threshold
        self._buckets: dict[tuple[int, tuple[int, ...]], list[int]] = {}
        self._signatures: list[list[int]] = []

    @staticmethod
    def _shingles(text: str, k: int = 5) -> set[str]:
        # пунктуация выбрасывается: "опять ставки, опять минус." и
        # "опять ставки опять минус" — одно сообщение, а по сырым шинглам
        # их сходство падает ниже порога
        norm = text.lower().replace("ё", "е")
        norm = re.sub(r"[^\w\s]+", " ", norm)
        norm = re.sub(r"\s+", " ", norm).strip()
        if len(norm) <= k:
            return {norm} if norm else set()
        return {norm[i : i + k] for i in range(len(norm) - k + 1)}

    def _signature(self, text: str) -> list[int]:
        shingles = self._shingles(text)
        if not shingles:
            return [0] * self.num_perm
        sig = []
        for seed in range(self.num_perm):
            best = min(
                int.from_bytes(
                    hashlib.blake2b(
                        s.encode("utf-8"), digest_size=8, salt=seed.to_bytes(8, "little")
                    ).digest(),
                    "little",
                )
                for s in shingles
            )
            sig.append(best)
        return sig

    @staticmethod
    def _similarity(a: list[int], b: list[int]) -> float:
        return sum(1 for x, y in zip(a, b) if x == y) / len(a)

    def is_duplicate(self, text: str) -> bool:
        """Проверяет и, если не дубликат, сразу запоминает сообщение."""
        sig = self._signature(text)
        candidates: set[int] = set()
        band_keys = []
        for b in range(self.bands):
            key = (b, tuple(sig[b * self.rows : (b + 1) * self.rows]))
            band_keys.append(key)
            candidates.update(self._buckets.get(key, ()))

        for idx in candidates:
            if self._similarity(sig, self._signatures[idx]) >= self.threshold:
                return True

        new_idx = len(self._signatures)
        self._signatures.append(sig)
        for key in band_keys:
            self._buckets.setdefault(key, []).append(new_idx)
        return False


# ------------------------------------------------------------------
#  Оркестрация
# ------------------------------------------------------------------

@dataclass
class CleaningStats:
    total_in: int = 0
    dropped: dict[str, int] = field(default_factory=dict)
    kept: int = 0

    def drop(self, reason: str) -> None:
        self.dropped[reason] = self.dropped.get(reason, 0) + 1


@dataclass
class CleaningResult:
    messages: list[InputMessage]
    stats: CleaningStats


def clean_messages(messages: list[InputMessage], use_ner: bool = False) -> CleaningResult:
    stats = CleaningStats(total_in=len(messages))
    deduper = MinHashDeduper()
    kept: list[InputMessage] = []

    for msg in messages:
        text = msg.text or ""

        if not text.strip():
            stats.drop("empty")
            continue
        if is_service_message(text):
            stats.drop("service")
            continue
        if looks_like_technical_output(text):
            stats.drop("technical_output")
            continue

        text = normalize(text)
        text = _EMAIL.sub("<EMAIL>", text)  # до ссылок: иначе домен почты уедет в <link:>
        text = replace_links(text)
        text = mask_pii(text)
        if use_ner:
            text = mask_names_ner(text)
        text = truncate(text)

        if not is_informative(text):
            stats.drop("not_informative")
            continue
        if deduper.is_duplicate(text):
            stats.drop("duplicate")
            continue

        kept.append(msg.model_copy(update={"text": text, "char_len": len(text)}))

    stats.kept = len(kept)
    return CleaningResult(messages=kept, stats=stats)

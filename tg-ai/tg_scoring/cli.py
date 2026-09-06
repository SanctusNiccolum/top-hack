"""
Консольный интерфейс.

    python -m tg_scoring.cli from-telegram result.json -o data/user1.json
    python -m tg_scoring.cli run              data/input.json -o out.json
    python -m tg_scoring.cli check            # диагностика подключения
    python -m tg_scoring.cli clean            data/sample_input.json
    python -m tg_scoring.cli prefilter-report data/sample_input.json
    python -m tg_scoring.cli prompt           data/sample_input.json --chunk 0
    python -m tg_scoring.cli analyze          data/sample_input.json -o out.json

Первые три команды не требуют ключа GigaChat — на них удобно настраивать
очистку и словарь маркеров до подключения модели.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from .chunking import make_chunks
from .cleaning import clean_messages
from .config import get_settings
from .markers import TOTAL_PATTERNS, find_marker_categories
from .prefilter import run_prefilter
from .prompts import SYSTEM_PROMPT, build_user_message
from .schemas import AnalyzeRequest


def load_request(path: str) -> AnalyzeRequest:
    return AnalyzeRequest.model_validate(json.loads(Path(path).read_text(encoding="utf-8")))


def load_any(path: str) -> tuple[AnalyzeRequest, str]:
    """Принимает любой из трёх форматов и сам понимает, какой это.

    Так `run` работает и с сырым payload бэкенда, и с выгрузкой Telegram
    Desktop, и с уже сконвертированным входом модуля — не заставляя
    помнить, какой конвертер вызывать.
    """
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("ожидался JSON-объект")

    if "texts" in data:
        from .backend_input import from_backend_payload

        request, _ = from_backend_payload(data)
        return request, "формат бэкенда {user_id, texts}"

    if "request_id" in data and "messages" in data:
        return AnalyzeRequest.model_validate(data), "готовый вход модуля"

    if "messages" in data:
        from .telegram_export import convert

        request, _ = convert(data)
        return request, "выгрузка Telegram Desktop"

    raise ValueError(
        "не удалось определить формат: нет ни texts, ни messages. "
        "Это точно файл с сообщениями?"
    )


def write_output(path: str, payload: str) -> bool:
    """Записать результат, создав недостающие папки.

    Path.write_text не создаёт родительские каталоги, поэтому `-o
    out\\user1.json` падал с FileNotFoundError, если папки out ещё нет.
    Само по себе это мелочь, но падало оно ПОСЛЕ запроса к GigaChat —
    то есть токены уже потрачены, а результат выброшен. Поэтому при
    любой ошибке записи payload печатается в stdout: перенаправить его
    в файл дешевле, чем гонять анализ заново.
    """
    target = Path(path)
    try:
        if target.parent and not target.parent.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(payload, encoding="utf-8")
        return True
    except OSError as exc:
        print(f"\nНе удалось записать {path}: {exc}", file=sys.stderr)
        print("Результат ниже — сохрани его вручную, анализ уже оплачен:\n",
              file=sys.stderr)
        print(payload)
        return False


def _rule(title: str = "") -> None:
    print(f"\n{'─' * 62}")
    if title:
        print(title)
        print("─" * 62)


def cmd_clean(args: argparse.Namespace) -> int:
    settings = get_settings()
    request = load_request(args.input)
    result = clean_messages(request.messages, use_ner=settings.pii_use_ner)

    _rule("ОЧИСТКА")
    print(f"на входе:  {result.stats.total_in}")
    print(f"осталось:  {result.stats.kept}")
    for reason, count in sorted(result.stats.dropped.items(), key=lambda x: -x[1]):
        print(f"  отсеяно [{reason}]: {count}")

    if args.show:
        _rule("ЧТО ОСТАЛОСЬ")
        for m in result.messages[: args.show]:
            cats = ",".join(sorted(find_marker_categories(m.text))) or "—"
            print(f"  {m.id}  [{cats}]  {m.text[:80]}")
    return 0


def cmd_prefilter_report(args: argparse.Namespace) -> int:
    settings = get_settings()
    request = load_request(args.input)
    cleaned = clean_messages(request.messages, use_ner=settings.pii_use_ner)
    result = run_prefilter(
        cleaned.messages,
        control_ratio=settings.prefilter_control_ratio,
        seed=settings.prefilter_seed,
    )

    _rule("ПРЕ-ФИЛЬТР")
    print(f"паттернов в словаре: {TOTAL_PATTERNS}")
    print(f"после очистки:       {result.total}")
    print(f"уйдёт в LLM:         {len(result.selected)}  "
          f"(маркеры {result.by_marker}, контроль {result.by_control})")
    if result.total:
        saved = 1 - len(result.selected) / result.total
        print(f"экономия вызовов:    {saved:.0%}")

    _rule("СРАБОТАВШИЕ КАТЕГОРИИ")
    for cat, count in sorted(result.marker_hits.items(), key=lambda x: -x[1]):
        print(f"  {cat:<24} {count}")

    _rule("КОНТРОЛЬНАЯ ВЫБОРКА (без маркеров)")
    print("Сигналы, которые LLM найдёт здесь, — это то, что недобирает словарь.\n")
    control = [m for m in result.selected if m.id in result.control_ids]
    for m in control:
        print(f"  {m.id}  {m.text[:80]}")
    if not control:
        print("  (пусто — увеличь PREFILTER_CONTROL_RATIO или объём данных)")
    return 0


def cmd_prompt(args: argparse.Namespace) -> int:
    settings = get_settings()
    request = load_request(args.input)
    cleaned = clean_messages(request.messages, use_ner=settings.pii_use_ner)
    selected = run_prefilter(
        cleaned.messages,
        control_ratio=settings.prefilter_control_ratio,
        seed=settings.prefilter_seed,
    ).selected
    chunks = make_chunks(selected, settings.chunk_size)
    if not chunks:
        print("нечего отправлять: после фильтров не осталось сообщений", file=sys.stderr)
        return 1
    if args.chunk >= len(chunks):
        print(f"чанков всего {len(chunks)}", file=sys.stderr)
        return 1

    if not args.user_only:
        _rule("SYSTEM")
        print(SYSTEM_PROMPT)
    _rule(f"USER (чанк {args.chunk} из {len(chunks)})")
    print(build_user_message(chunks[args.chunk]))
    return 0


def cmd_from_telegram(args: argparse.Namespace) -> int:
    """result.json из Telegram Desktop -> готовый вход модуля."""
    from .telegram_export import convert_file

    request, stats = convert_file(
        args.input,
        period_days=args.days,
        author=args.author,
        auto_author=not args.all_authors,
        anchor=args.anchor,
        request_id=args.request_id,
    )

    _rule("КОНВЕРТАЦИЯ ЭКСПОРТА")
    print(f"  сообщений в файле : {stats['total']}")
    print(f"  служебных         : {stats['service']}")
    print(f"  без текста        : {stats['empty']}")
    print(f"  чужих авторов     : {stats['other_author']}")
    print(f"  старше {args.days} дней  : {stats['too_old']}")
    print(f"  ОСТАЛОСЬ          : {stats['kept']}")
    print(f"  тип источника     : {request.source.kind}")

    if stats["kept"] < 30:
        print("\n  ⚠ Меньше 30 сообщений — модуль вернёт insufficient_data.")
        print("    Увеличь --days или возьми более активный канал.")
    if stats["other_author"] == 0 and request.source.kind == "chat":
        print("\n  ⚠ Фильтр по автору ничего не отсеял. Проверь, что в экспорте")
        print("    действительно один автор, иначе укажи --author явно.")

    payload = json.dumps(request.model_dump(mode="json"), ensure_ascii=False, indent=2)
    write_output(args.output, payload)
    print(f"\nЗаписано: {args.output}")
    print(f"Дальше:   python -m tg_scoring.cli analyze {args.output} -o out.json")
    return 0


def cmd_from_backend(args: argparse.Namespace) -> int:
    """Плоский {user_id, texts} от бэкенда -> вход модуля."""
    from .backend_input import from_backend_file

    request, warnings = from_backend_file(
        args.input,
        request_id=args.request_id,
        source_kind=args.kind,
    )
    payload = json.dumps(request.model_dump(mode="json"), ensure_ascii=False, indent=2)
    write_output(args.output, payload)

    _rule("КОНВЕРТАЦИЯ")
    print(f"  сообщений на входе: {request.source.messages_raw}")
    print(f"  записано:           {len(request.messages)}")
    print(f"  request_id:         {request.request_id}")
    print(f"  результат:          {args.output}")

    if warnings:
        _rule("ПРЕДУПРЕЖДЕНИЯ")
        for w in warnings:
            print(f"  ⚠ {w}")

    print("\nДальше:")
    print(f"  python -m tg_scoring.cli clean {args.output}")
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    """Пошаговая диагностика: ключ -> токен -> модели -> тестовый запрос.

    Сделано отдельными шагами намеренно: 401 почти никогда не про промпт,
    он про авторизацию, и важно видеть, на каком именно шаге всё встало.
    """
    from .llm import GigaChatProvider, LLMError

    settings = get_settings()

    _rule("КОНФИГУРАЦИЯ")
    print(f"  base url : {settings.gigachat_base_url}")
    print(f"  chat url : {settings.gigachat_api_url}")
    print(f"  scope    : {settings.gigachat_scope}")
    print(f"  модель   : {settings.gigachat_model}")
    print(f"  verify   : {settings.verify_ssl!r}")
    key = settings.gigachat_auth_key
    print(f"  ключ     : {'задан (' + str(len(key)) + ' симв.)' if key else 'НЕ ЗАДАН'}")

    if not key:
        print("\n[1/3] ключ    ✗  GIGACHAT_AUTH_KEY пуст")
        print("      Скопируй .env.example в .env и вставь ключ авторизации")
        print("      из личного кабинета developers.sber.ru.")
        return 2

    _rule("ПРОВЕРКА")
    try:
        provider = GigaChatProvider(settings)
        provider._get_token()
        print("[1/3] токен    ✓  авторизация прошла")
    except LLMError as exc:
        print(f"[1/3] токен    ✗  {exc}")
        _hint(exc)
        return 2

    try:
        models = provider.list_models()
        print(f"[2/3] модели   ✓  доступно {len(models)}: {', '.join(models)}")
        if settings.gigachat_model not in models:
            print(f"      ⚠ GIGACHAT_MODEL={settings.gigachat_model} нет в списке.")
            print(f"      Поставь в .env одну из перечисленных выше.")
    except LLMError as exc:
        print(f"[2/3] модели   ✗  {exc}")
        _hint(exc)
        return 2

    try:
        answer = provider.ping()
        print(f"[3/3] генерация ✓  модель ответила: {answer.strip()[:60]!r}")
    except LLMError as exc:
        print(f"[3/3] генерация ✗  {exc}")
        _hint(exc)
        return 2

    print("\nВсё работает. Можно запускать:")
    print("  python -m tg_scoring.cli analyze data/sample_input.json -o out.json")
    return 0


def _hint(exc: Exception) -> None:
    text = str(exc).lower()
    if "certificate" in text or "ssl" in text:
        print("      → Проблема с сертификатом НУЦ Минцифры. Варианты:")
        print("        GIGACHAT_VERIFY_SSL=false            (быстро, только для отладки)")
        print("        GIGACHAT_VERIFY_SSL=C:\\path\\ca.crt   (правильно)")
        print("        Сертификат: https://gu-st.ru/content/lending/russian_trusted_root_ca_pem.crt")
    elif "401" in text or "unauthor" in text:
        print("      → Ключ или scope неверны. Ключ авторизации из кабинета уже в base64,")
        print("        второй раз кодировать его не надо. Для физлица scope=GIGACHAT_API_PERS.")
    elif "404" in text:
        print("      → Похоже на неверный адрес. С 17.07.2026 базовый адрес — https://api.giga.chat")
        print("        Старый gigachat.devices.sberbank.ru работает только у подключившихся ранее.")
    elif "402" in text or "quota" in text or "limit" in text:
        print("      → Закончились токены. Проверь баланс в кабинете developers.sber.ru.")


def cmd_analyze(args: argparse.Namespace) -> int:
    from .llm import GigaChatProvider, LLMError  # импорт здесь: requests нужен только тут
    from .pipeline import analyze

    settings = get_settings()
    request = load_request(args.input)
    try:
        provider = GigaChatProvider(settings)
    except LLMError as exc:
        print(f"Ошибка: {exc}", file=sys.stderr)
        return 2

    collected: list = []
    response = analyze(request, provider, settings, on_signals=collected.extend)
    payload = json.dumps(response.model_dump(mode="json"), ensure_ascii=False, indent=2)

    if getattr(args, "dump_signals", None):
        dump = [
            {"category": x.category, "confidence": x.confidence, "modality": x.modality}
            for x in collected
        ]
        write_output(args.dump_signals, json.dumps(dump, ensure_ascii=False, indent=2))
        print(f"сигналы сохранены в {args.dump_signals}")

    if args.output:
        write_output(args.output, payload)
        print(f"результат записан в {args.output}")
    else:
        print(payload)
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    """Один вызов: любой формат на входе -> готовый результат.

    Конвертация, очистка и пре-фильтр происходят ВНУТРИ пайплайна —
    отдельно запускать `clean` не нужно. Команды `clean` и
    `prefilter-report` существуют, чтобы посмотреть глазами, а не как
    обязательный шаг.
    """
    from .llm import GigaChatProvider, LLMError
    from .pipeline import analyze

    settings = get_settings()
    try:
        request, detected = load_any(args.input)
    except ValueError as exc:
        print(f"Ошибка: {exc}", file=sys.stderr)
        return 1

    _rule("ВХОД")
    print(f"  файл:       {args.input}")
    print(f"  формат:     {detected}")
    print(f"  сообщений:  {len(request.messages)}")
    print(f"  request_id: {request.request_id}")

    try:
        provider = GigaChatProvider(settings)
    except LLMError as exc:
        print(f"\nОшибка: {exc}", file=sys.stderr)
        print("Проверь подключение: python -m tg_scoring.cli check", file=sys.stderr)
        return 2

    collected: list = []
    response = analyze(request, provider, settings, on_signals=collected.extend)
    payload = json.dumps(response.model_dump(mode="json"), ensure_ascii=False, indent=2)

    if args.dump_signals:
        dump = [
            {"category": x.category, "confidence": x.confidence, "modality": x.modality}
            for x in collected
        ]
        write_output(args.dump_signals, json.dumps(dump, ensure_ascii=False, indent=2))
        print(f"\n  сигналы сохранены в {args.dump_signals} "
              f"(подбор весов: cli.py tune {args.dump_signals})")

    _rule("РЕЗУЛЬТАТ")
    print(f"  статус:        {response.status.value}")
    print(f"  дельта:        {response.score_delta:+.1f}")
    print(f"  риск:          {response.risk_level.value}")
    print(f"  уверенность:   {response.confidence}")
    if response.coverage:
        print(f"  проанализировано: {response.coverage.messages_analyzed} "
              f"(с сигналами: {response.coverage.messages_with_signal})")
    if response.factors:
        print("  факторы:")
        for f in response.factors:
            print(f"    {f.contribution:+6.1f}  {f.category} ({f.evidence_count})")
    if response.explanation_ru:
        print(f"\n  {response.explanation_ru}")

    if not write_output(args.output, payload):
        return 3
    print(f"\n  записано в {args.output}")
    return 0


def cmd_tune(args: argparse.Namespace) -> int:
    """Подбор строгости по сохранённым сигналам, без обращения к LLM.

    Разметка стоит токенов, арифметика — нет. Один раз сохранил сигналы
    через --dump-signals, дальше крутишь параметры сколько угодно.
    """
    from .aggregator import aggregate
    from .config import ScoringConfig
    from .validation import AcceptedSignal

    raw = json.loads(Path(args.input).read_text(encoding="utf-8"))
    signals = [
        AcceptedSignal("m", x["category"], x["confidence"], x.get("modality", "fact"), "q")
        for x in raw
    ]
    if not signals:
        print("В файле нет принятых сигналов — крутить нечего.", file=sys.stderr)
        print("Это и есть диагноз: смотри meta.signals_rejected в результате.",
              file=sys.stderr)
        return 1

    base = get_settings().scoring
    n = args.messages

    _rule("ЧТО ЕСТЬ")
    by_cat: dict[str, int] = {}
    for s_ in signals:
        by_cat[s_.category] = by_cat.get(s_.category, 0) + 1
    print(f"  принятых сигналов: {len(signals)}   сообщений: {n}")
    for cat, count in sorted(by_cat.items(), key=lambda kv: -kv[1]):
        print(f"    {count:>3}  {cat}")

    scales = [float(x) for x in args.scales.split(",")]
    ks = [float(x) for x in args.k.split(",")]

    _rule("ДЕЛЬТА ПРИ РАЗНЫХ НАСТРОЙКАХ")
    print("  строки — TANH_SCALE (меньше = строже), столбцы — SATURATION_K\n")
    print("           " + "".join(f"k={k:<8}" for k in ks))
    for scale in scales:
        cells = []
        for k in ks:
            cfg = ScoringConfig(
                min_confidence_positive=base.min_confidence_positive,
                min_confidence_negative=base.min_confidence_negative,
                saturation_k=k,
                tanh_scale=scale,
                coverage_target_messages=base.coverage_target_messages,
                min_messages_for_verdict=base.min_messages_for_verdict,
            )
            result = aggregate(signals, n, cfg)
            cells.append(f"{result.score_delta:+7.1f}  ")
        print(f"  scale={scale:<5}" + "".join(cells))

    current = aggregate(signals, n, base)
    _rule("СЕЙЧАС")
    print(f"  TANH_SCALE={base.tanh_scale}  SATURATION_K={base.saturation_k}  "
          f"COVERAGE_TARGET_MESSAGES={base.coverage_target_messages}")
    print(f"  дельта {current.score_delta:+.1f}   риск {current.risk_level.value}   "
          f"сырая сумма вкладов {current.delta_raw:+.2f}")
    print("\n  Выбранные значения пропиши в .env и перезапусти analyze.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="tg_scoring", description=__doc__)
    parser.add_argument("-v", "--verbose", action="store_true", help="подробные логи")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("clean", help="показать результат очистки (без GigaChat)")
    p.add_argument("input")
    p.add_argument("--show", type=int, default=20, help="сколько сообщений вывести")
    p.set_defaults(func=cmd_clean)

    p = sub.add_parser("prefilter-report", help="отчёт по пре-фильтру (без GigaChat)")
    p.add_argument("input")
    p.set_defaults(func=cmd_prefilter_report)

    p = sub.add_parser("prompt", help="показать точный промпт для чанка (без GigaChat)")
    p.add_argument("input")
    p.add_argument("--chunk", type=int, default=0)
    p.add_argument("--user-only", action="store_true")
    p.set_defaults(func=cmd_prompt)

    p = sub.add_parser("from-telegram", help="result.json из Telegram Desktop -> вход модуля")
    p.add_argument("input", help="путь к result.json")
    p.add_argument("-o", "--output", required=True, help="куда записать вход модуля")
    p.add_argument("--days", type=int, default=90, help="окно анализа, по умолчанию 90")
    p.add_argument("--author", help="from_id или имя автора; по умолчанию определяется автоматически")
    p.add_argument("--all-authors", action="store_true",
                   help="не фильтровать по автору (для канала одного человека)")
    p.add_argument("--anchor", choices=["now", "last"], default="now",
                   help="от чего отмерять окно: от сегодня или от последнего сообщения "
                        "(last спасает старую выгрузку)")
    p.add_argument("--request-id", help="свой request_id вместо случайного uuid")
    p.set_defaults(func=cmd_from_telegram)

    p = sub.add_parser("from-backend", help="{user_id, texts} от бэкенда -> вход модуля")
    p.add_argument("input", help="json от бэкенда")
    p.add_argument("-o", "--output", required=True, help="куда записать вход модуля")
    p.add_argument("--kind", choices=["channel", "chat"], default="chat",
                   help="что за источник; chat означает более осторожную атрибуцию")
    p.add_argument("--request-id", help="свой request_id вместо u<user_id>")
    p.set_defaults(func=cmd_from_backend)

    p = sub.add_parser("check", help="проверить ключ, модели и связь с GigaChat")
    p.set_defaults(func=cmd_check)

    p = sub.add_parser("run", help="всё сразу: любой формат -> результат (нужен ключ)")
    p.add_argument("input", help="payload бэкенда, выгрузка Telegram или готовый вход")
    p.add_argument("-o", "--output", default="out.json")
    p.add_argument("--dump-signals", metavar="FILE",
                   help="сохранить принятые сигналы для подбора весов через tune")
    p.set_defaults(func=cmd_run)

    p = sub.add_parser("tune", help="подобрать строгость по сохранённым сигналам (без GigaChat)")
    p.add_argument("input", help="файл из --dump-signals")
    p.add_argument("--messages", type=int, default=150,
                   help="сколько было сообщений после очистки (для coverage)")
    p.add_argument("--scales", default="20,15,12,10,8",
                   help="какие TANH_SCALE перебрать")
    p.add_argument("--k", default="3,2", help="какие SATURATION_K перебрать")
    p.set_defaults(func=cmd_tune)

    p = sub.add_parser("analyze", help="полный прогон через GigaChat")
    p.add_argument("input")
    p.add_argument("-o", "--output")
    p.add_argument("--dump-signals", metavar="FILE",
                   help="сохранить принятые сигналы для подбора весов через tune")
    p.set_defaults(func=cmd_analyze)

    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
    )
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())

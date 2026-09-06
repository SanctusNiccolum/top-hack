## Если при поднятии докера не применяются миграции, запути вручную!
(там проблемс с ссылкой подключени к бд могут быть)

```
cd backend
alembic upgrade head
```
(делаем после поднятия бд без приложения, и удаляем в докерфайле строку с запуском этого скрипта, если с ней всё ещё не работает)


Пример .env для запуска

```
POSTGRES_USER=postgres
POSTGRES_PASSWORD=123
POSTGRES_DB=postgres
DATABASE_URL=postgresql+asyncpg://postgres:123@db/postgres
DATABASE_URL_SYNC=postgresql+psycopg2://postgres:123@db/postgres

# Для POST /telegram/analyze (запуск telegram_parser/) — одна пара
# api_id/api_hash на весь сервис, получить на https://my.telegram.org
TG_API_ID=...
TG_API_HASH=...
```

## /telegram/* — весь код в app/telegram_analysis/

Все эндпоинты требуют обычный Bearer-токен нашего сервиса (тот же
`get_current_user`, что и везде) — это не замена telegram-логину, а
проверка, что дёргает залогиненный пользователь бэкенда.

1. `POST /telegram/login/phone {phone_number}` → `{login_id}`. Живой
   Telethon-клиент создаётся и держится в памяти backend-процесса, пока
   пользователь не введёт код (TTL 15 минут).
2. `POST /telegram/login/code {login_id, code}` → `{status: "ok" | "need_password", session_string?, telegram_user_id?}`.
3. Если `need_password` — `POST /telegram/login/password {login_id, password}` → тот же формат ответа, уже с `session_string`.
   На успехе (в шаге 2 или 3) `telegram_user_id` сохраняется в
   `user_profile.tg_user_id` текущего пользователя (миграция
   `d4b8a2f6c9e1_add_tg_user_id_to_user_profile`) — это реальный numeric
   Telegram ID, он НЕ совпадает с `user_profile.user_id` (тот — внутренний,
   назначается при регистрации по телефону, до всякого Telegram).
4. `POST /telegram/chats {session_string}` → список диалогов
   `{chat_id, name, username, type}`, `type` определяется автоматически
   (`own_messages` / `subscription`), фронт даёт юзеру выбрать чекбоксами.
5. `POST /telegram/analyze {session_string, chat_ids}` → `202 {"status": "started"}`.
   Тонкая обёртка над `telegram_parser/` (сам парсер — отдельный пакет в
   корне репозитория, здесь только вызов подпроцессом, fire-and-forget).
   Результат смотреть в таблицах `parse_state`/`ai_queue`, которые создаёт
   парсер (миграция `c1a4f9d3e7b2_add_telegram_parser_tables`) — по
   `parse_state.user_id`, который равен `telegram_user_id` из шага 2/3, а не
   `user_profile.user_id`. Статус-эндпоинта, который сам делал бы этот join
   и отдавал готовый ответ по Bearer-токену, пока нет.

`session_string` одноразовый: `telegram_parser/main.py` сам вызывает
`log_out()` в конце ЛЮБОГО запуска `/telegram/analyze` (успех или ошибка) —
значит после первого анализа его нельзя переиспользовать, нужен новый
проход через `/telegram/login/*`.
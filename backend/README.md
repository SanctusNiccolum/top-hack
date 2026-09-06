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
```
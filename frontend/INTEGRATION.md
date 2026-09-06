# Подключение фронта к бэкенду

Сейчас фронт не делает ни одного запроса к API — всё живёт в `localStorage`.
Ниже что нужно, чтобы это заработало.

## 0. Куда класть файлы

Судя по импортам в `App.jsx` (`./pages/...`, `./components/...`,
`./theme/config.js`), в репозитории лежит **не** рабочая структура проекта —
файлы залиты плоско. Разложить так:

```
src/
  api.js                       <- новый файл (лежит здесь как frontend/api.js)
  pages/TelegramAnalysisPage.jsx  <- заменить (переписан целиком)
  pages/StatementUploadPage.jsx   <- новый файл
```

## 1. Адрес бэкенда

Создать `.env` в корне фронта:

```
VITE_API_URL=http://localhost:8001
```

Без него `api.js` возьмёт `http://localhost:8001` по умолчанию — это адрес
из `docker-compose.yaml`.

CORS на бэкенде уже разрешён, отдельно настраивать ничего не нужно.

## 2. Роут для загрузки выписки

В `App.jsx`, рядом с остальными:

```jsx
import StatementUploadPage from './pages/StatementUploadPage';

<Route
  path="/statement"
  element={isAuthenticated ? <StatementUploadPage /> : <Navigate to="/" replace />}
/>
```

## 3. Авторизация — главное, что нужно поменять

Сейчас `RegistrationModal` просто пишет в `localStorage` и считает
пользователя залогиненным. Нужно реально звать бэкенд:

```jsx
import { register, login } from '../api';

// регистрация
const data = await register(phoneNumber, password);
// вход
const data = await login(phoneNumber, password);
```

Обе функции сами сохраняют токен, дальше все запросы уходят уже с ним.
Требования бэкенда: пароль **не короче 8 символов**, телефон 5–20 символов.

## 4. Анкета

```jsx
import { updateAccount, completeAccount } from '../api';

await updateAccount({ age: 21, city: 'Екатеринбург', monthly_income: 45000 });
await completeAccount();   // без этого /report ответит «Анкета ещё не завершена»
```

`updateAccount` принимает частичные данные — можно слать по шагам анкеты.
Имена полей — в точности как в бэкенде (`snake_case`), список полей см.
`backend/app/api/schemas/account.py`.

## 5. Рейтинг

```jsx
import { createReport } from '../api';

const report = await createReport({ monthlyPayments: 9800 });
// report.score            — итог 0..100
// report.survey_score     — ветка «анкета»
// report.statement_score  — ветка «выписка»
// report.telegram_score   — ветка «telegram» (пока null: ИИ-часть не готова)
```

Ветка со значением `null` ещё не считалась — на странице рейтинга такие
блоки лучше показывать как «не заполнено», а не как ноль баллов: в расчёте
итога они не участвуют, их вес перераспределяется на остальные.

## 6. Согласие — обязательно перед Telegram

Бэкенд **не запустит** разбор Telegram без записи согласия: `/telegram/analyze`
ответит `403`. Перед запуском анализа нужно вызвать:

```jsx
import { grantConsent } from '../api';

await grantConsent('telegram_analysis', 'v1');
```

Чекбокс с текстом согласия должен быть на экране до кнопки «Анализировать».
Отозвать: `revokeConsent('telegram_analysis')` — после этого анализ снова
блокируется. Типы: `telegram_analysis`, `bank_statement`, `personal_data`.

## 7. Telegram

Готовая страница `TelegramAnalysisPage.jsx` уже проходит весь путь:
телефон → код → пароль 2FA (если включён) → выбор чатов → запуск разбора →
опрос статуса.

Что важно знать:

- Войти **по @юзернейму нельзя** — только по номеру телефона, это
  ограничение протокола Telegram. Старый текст «номер или юзернейм» убран.
- Сессия Telegram **одноразовая**: после запуска анализа она отзывается,
  повторный анализ требует нового входа.
- Разбор идёт в фоне, поэтому страница опрашивает `/telegram/status`
  раз в 2 секунды, пока не придёт `done` или `failed`.

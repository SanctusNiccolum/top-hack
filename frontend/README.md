# Frontend — альтернативный скоринг

Клиентская часть сервиса: лендинг, анкета, загрузка выписки, подключение
Telegram и страница рейтинга. Все данные приходят с бэкенда — на клиенте
ничего не считается.

## Основной принцип оценки

Итоговый скоринг строится из нескольких независимых веток:

1. **Анкета** пользователя — шкала 0..100
2. **Банковская выписка** — шкала 0..100
3. **Telegram-активность** — это **поправка** −25..+25, а не балл

```
итог = clamp(среднее(анкета, выписка) + telegram_delta, 0, 100)
```

Telegram устроен иначе двух других намеренно: он не даёт самостоятельной
оценки платёжеспособности, а корректирует её. Если бы он усреднялся
наравне с остальными, нейтральный результат (дельта 0, то есть 50 баллов
в шкале 0..100) тянул бы вниз хорошего заёмщика.

## Стек

React 18, Vite, React Router, Styled Components, Storybook, Prop Types.

## Структура

```text
src/
  api.js                  клиент бэкенда — все запросы идут через него
  App.jsx, main.jsx, styles.css
  components/
    RegistrationModal.jsx вход и регистрация (режим задаётся пропом mode)
  pages/
    AccountPage.jsx       личный кабинет
    RatingPage.jsx        итоговая оценка и разбивка по веткам
    ProfilePage.jsx
    SurveyPage.jsx        анкета, 4 шага
    StatementUploadPage.jsx  загрузка PDF-выписки
    TelegramAnalysisPage.jsx телефон -> код -> 2FA -> выбор чатов -> анализ
  theme/config.js         параметры оформления
  utils/
    surveyToAccount.js    ответы анкеты -> поля API (enum-коды)
    recommendations.js    рекомендации из посчитанных факторов
```

## Запуск

```bash
npm install
npm run dev
```

Дополнительно: `npm run build`, `npm run preview`, `npm run storybook`,
`npm test`.

### Адрес бэкенда

`.env` в корне фронта:

```
VITE_API_URL=http://localhost:8001
```

Без него `api.js` возьмёт этот же адрес по умолчанию — он совпадает с
`docker-compose.yaml`. Для доступа с другого устройства укажите здесь IP
машины, где поднят бэкенд (`localhost` на телефоне будет означать сам
телефон). CORS на бэкенде разрешён, настраивать ничего не нужно.

---

# Контракты API

## Авторизация

```jsx
import { register, login } from '../api';

await register(phoneNumber, password);
await login(phoneNumber, password);
```

Обе функции сами сохраняют токен, дальше запросы уходят уже с ним.

**Вход идёт по номеру телефона, не по email** — так устроен бэкенд
(`LoginRequest`), email хранится в профиле и в аутентификации не
участвует. Пароль — не короче 8 символов, телефон 5–20.

## Анкета

```jsx
import { updateAccount, completeAccount } from '../api';

await updateAccount(surveyToAccount(answers, user));
await completeAccount();   // без этого /report ответит «Анкета ещё не завершена»
```

`updateAccount` принимает частичные данные — можно слать по шагам. Имена
полей `snake_case`, как в `backend/app/api/schemas/account.py`. Перевод
человеческих ответов («Замужем/Женат») в enum-коды (`MARRIED`) лежит в
`utils/surveyToAccount.js` — если формулировка в анкете меняется, править
нужно только там.

## Рейтинг

```jsx
const report = await createReport({ monthlyPayments: 9800 });
// report.score             итог 0..100
// report.survey_score      ветка «анкета»
// report.statement_score   ветка «выписка»
// report.telegram_delta    поправка −25..+25 (НЕ балл)
// report.telegram_risk     'low' | 'medium' | 'high' | 'insufficient_data'
// report.telegram_comment  объяснение на русском
// report.telegram_factors  [{category, contribution, evidence_count}]
```

Ветка со значением `null` ещё не считалась — показывайте «не заполнено»,
а не ноль баллов: в расчёте итога такие ветки не участвуют, их вес
переходит на остальные.

**`monthlyPayments` обязательно передавать** — это сумма ежемесячных
платежей по кредитам, ключевой вход формулы ПДН. Без неё база всегда
равна 100 и анкетная ветка выдаёт максимум всем подряд.

## Согласие

Бэкенд не примет ни выписку, ни разбор Telegram без записи согласия —
ответит `403`:

```jsx
await grantConsent('telegram_analysis', 'v1');   // или 'bank_statement'
```

Отозвать: `revokeConsent(type)`. Типы: `telegram_analysis`,
`bank_statement`, `personal_data`. Чекбокс с текстом согласия должен
быть на экране до кнопки запуска.

## Telegram

`TelegramAnalysisPage` проходит весь путь одной страницей: телефон → код
→ пароль 2FA (если включён) → выбор чатов → запуск разбора → опрос
статуса → запуск ИИ-анализа.

- **Войти по @юзернейму нельзя** — только по номеру телефона, это
  ограничение протокола Telegram, а не бэкенда.
- **Сессия одноразовая**: парсер отзывает её в конце любого запуска,
  повторный анализ требует нового входа с новым кодом.
- Разбор идёт в фоне, поэтому страница опрашивает `/telegram/status`
  раз в 2 секунды, пока не придёт `done` или `failed`.
- После `done` автоматически вызывается `/telegram/score` — он считает
  поправку по текстам (GigaChat) и по подпискам на каналы.

## Загрузка выписки

```jsx
await grantConsent('bank_statement', 'v1');
const result = await uploadStatement(file);
```

Запрос синхронный, скор возвращается сразу. Принимается PDF с текстовым
слоем — скан не подойдёт, операции из него не извлекаются.

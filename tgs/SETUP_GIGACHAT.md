 Как подключить GigaChat

Пять шагов. Дольше всего — регистрация, остальное минут десять.

---

## 1. Аккаунт и проект

1. Зайди на **developers.sber.ru**, войди через Сбер ID или почту.
2. В разделе **GigaChat API** создай проект, тип — **для физических лиц**
   (это бесплатный тариф, `scope = GIGACHAT_API_PERS`).
3. Подтверди телефон, если попросит.

Новым пользователям при регистрации дают **1 миллион токенов**. Для
хакатона это очень много: один прогон нашего модуля на канале в 640
сообщений — это примерно 15–25 тысяч токенов, то есть десятки полных
прогонов из подарочного пакета.

---

## 2. Ключ авторизации

В проекте нажми **сгенерировать ключ** (в интерфейсе это «Ключ
авторизации» / Authorization key). Ты получишь длинную строку вида
`MWJkNzQ4YzMt...==`.

Три вещи, на которых спотыкаются все:

**Ключ показывается один раз.** Закроешь окно — придётся генерировать
новый. Сразу вставь его в `.env`.

**Это уже base64.** Внутри зашит `client_id:client_secret`. Кодировать его
второй раз не надо — просто вставь как есть.

**Это не токен доступа.** Ключ вечный, а токен, который по нему выдаётся,
живёт 30 минут. Наш код обновляет токен сам, руками ничего делать не надо.

Открой `.env` и впиши:

```
GIGACHAT_AUTH_KEY=MWJkNzQ4YzMt...==
GIGACHAT_SCOPE=GIGACHAT_API_PERS
```

---

## 3. Сертификаты

Это причина примерно половины «у меня ничего не работает» с GigaChat.

Домены Сбера подписаны сертификатом **НУЦ Минцифры**, которого нет ни в
стандартном хранилище Windows, ни в `certifi`, откуда сертификаты берёт
Python. Без него `requests` падает с `SSL: CERTIFICATE_VERIFY_FAILED`.

**Быстро, для отладки:**

```
GIGACHAT_VERIFY_SSL=false
```

Работает сразу, но отключает проверку подлинности сервера. Для хакатона
допустимо, для чего-то настоящего — нет.

**Правильно:** скачай корневой сертификат

```
https://gu-st.ru/content/lending/russian_trusted_root_ca_pem.crt
```

и укажи путь к нему:

```
GIGACHAT_VERIFY_SSL=C:\Users\Gisha\Desktop\hakaton\russian_trusted_root_ca_pem.crt
```

Либо добавь его в хранилище Python один раз на все проекты:

```bash
# Linux / macOS
curl -k https://gu-st.ru/content/lending/russian_trusted_root_ca_pem.crt >> $(python -m certifi)
```

```powershell
# Windows PowerShell
$certifi = python -m certifi
Invoke-WebRequest -Uri "https://gu-st.ru/content/lending/russian_trusted_root_ca_pem.crt" `
  -OutFile "$env:TEMP\ru_ca.crt" -SkipCertificateCheck
Get-Content "$env:TEMP\ru_ca.crt" | Add-Content $certifi
```

После этого можно ставить `GIGACHAT_VERIFY_SSL=true`.

---

## 4. Проверка

```bash
python -m tg_scoring.cli check
```

Команда идёт по шагам и показывает, на каком именно всё встало:

```
[1/3] токен     ✓  авторизация прошла
[2/3] модели    ✓  доступно 3: GigaChat-2-Lite, GigaChat-2-Pro, GigaChat-2-Max
[3/3] генерация ✓  модель ответила: 'тест'
```

Шаги разделены намеренно: **401 почти никогда не про промпт**, он про
авторизацию, и полезно сразу видеть, это ключ, сертификат или модель.

Второй шаг заодно печатает точные идентификаторы моделей, доступные
твоему ключу, — поставь один из них в `GIGACHAT_MODEL`, чтобы не гадать.

---

## 5. Запуск

```bash
python -m tg_scoring.cli analyze data/sample_input.json -o out.json
```

---

## Что делать, если

| Симптом | Причина | Что сделать |
|---|---|---|
| `CERTIFICATE_VERIFY_FAILED` | нет сертификата Минцифры | шаг 3 |
| `401 Unauthorized` | неверный ключ или scope | ключ уже base64, не кодируй повторно; для физлица `GIGACHAT_API_PERS` |
| `404` на chat/completions | старый адрес API | `GIGACHAT_BASE_URL=https://api.giga.chat` |
| модель не найдена | неверный `GIGACHAT_MODEL` | возьми id из вывода `check` |
| `402` / закончились токены | исчерпан пакет | баланс в кабинете developers.sber.ru |
| работает, но JSON рвётся | модель добавляет текст вокруг | это уже обработано: парсер снимает markdown-фенс, при неудаче идёт repair-ретрай |

---

## Как это устроено внутри

Две HTTP-операции, обе в `tg_scoring/llm/gigachat.py`:

**Получение токена.** `POST https://ngw.devices.sberbank.ru:9443/api/v2/oauth`
с заголовками `Authorization: Basic <ключ>`, `RqUID: <uuid4>`,
`Content-Type: application/x-www-form-urlencoded` и телом `scope=...`.
В ответ — `access_token` и `expires_at`. Код кеширует токен и обновляет
его за минуту до истечения, так что на 16 чанков уходит один запрос
токена, а не шестнадцать.

**Запрос к модели.** `POST https://api.giga.chat/v1/chat/completions` с
`Authorization: Bearer <токен>` и телом в формате, совместимом с OpenAI:
`model`, `messages`, `temperature`, `top_p`. Ответ забирается из
`choices[0].message.content`.

Температура у нас `0.1`, а не `0`: ноль API может не принять, а нам нужна
максимальная воспроизводимость разметки. Если увидишь расхождение больше
2 баллов между прогонами одного входа — первым делом проверь, что
температура не уехала вверх.

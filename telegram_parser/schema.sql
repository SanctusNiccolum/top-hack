-- Схема таблиц, которыми владеет и в которые пишет Telegram-парсер.
-- Таблицы users/profile/occupation/... из общей схемы проекта сюда не входят —
-- парсер работает независимо от них, зная только числовой user_id.

CREATE TABLE IF NOT EXISTS trusted_channels (
    trusted_channel_id  BIGSERIAL PRIMARY KEY,
    username            TEXT NOT NULL UNIQUE,   -- @username канала, БЕЗ @
    category            TEXT,                    -- 'finance', 'gambling', 'job', ...
    display_name        TEXT                     -- человекочитаемая подпись для админки
);
-- Наполняется командой отдельно; пока намеренно пустая.

CREATE TABLE IF NOT EXISTS subscriptions (
    subscription_id     BIGSERIAL PRIMARY KEY,
    user_id             BIGINT NOT NULL,
    chat_id             BIGINT NOT NULL,
    channel_name        TEXT,                    -- title на момент парсинга (для отображения, не для сверки)
    username            TEXT,                    -- @username — по нему идёт сверка с trusted_channels
    about               TEXT,                    -- описание канала (GetFullChannelRequest)
    trusted_channel_id  BIGINT REFERENCES trusted_channels(trusted_channel_id),
    detected_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (user_id, chat_id)
);

CREATE TABLE IF NOT EXISTS messages (
    msg_id       BIGSERIAL PRIMARY KEY,           -- internal id; на него ссылается message_analysis (схема ИИ-команды)
    tg_msg_id    BIGINT NOT NULL,                 -- «сырой» id сообщения из Telegram (уникален только внутри чата)
    user_id      BIGINT NOT NULL,
    chat_id      BIGINT NOT NULL,
    chat_name    TEXT,
    chat_type    TEXT,
    datetime     TIMESTAMPTZ NOT NULL,
    text         TEXT NOT NULL,                   -- уже PII-очищен и прошёл фильтр длины
    is_forward   BOOLEAN NOT NULL DEFAULT FALSE,
    is_reply     BOOLEAN NOT NULL DEFAULT FALSE,
    UNIQUE (chat_id, tg_msg_id)                    -- защита от дублей при инкрементальном парсинге
);

CREATE TABLE IF NOT EXISTS parse_state (
    user_id         BIGINT NOT NULL,
    chat_id         BIGINT NOT NULL,
    last_parsed_at  TIMESTAMPTZ,
    status          TEXT,               -- 'success' | 'failed'
    error_message   TEXT,
    PRIMARY KEY (user_id, chat_id)
);

CREATE TABLE IF NOT EXISTS ai_queue (
    queue_id       BIGSERIAL PRIMARY KEY,
    user_id        BIGINT NOT NULL,
    status         TEXT NOT NULL DEFAULT 'pending',  -- 'pending' | 'processing' | 'done' | 'failed'
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    processed_at   TIMESTAMPTZ,
    error_message  TEXT
);

CREATE INDEX IF NOT EXISTS idx_ai_queue_status ON ai_queue (status);
CREATE INDEX IF NOT EXISTS idx_messages_user ON messages (user_id);
CREATE INDEX IF NOT EXISTS idx_subscriptions_user ON subscriptions (user_id);

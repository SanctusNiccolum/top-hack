"""add telegram parser tables

Таблицы, которыми владеет telegram_parser (см. telegram_parser/schema.sql в
корне репозитория) — не описаны через SQLAlchemy-модели, так как парсер
пишет в них напрямую через asyncpg, независимо от ORM-моделей бэкенда.
Ключи этих таблиц (user_id) — реальный numeric Telegram ID, а не
user_profile.user_id бэкенда, это разные пространства идентификаторов.

Revision ID: c1a4f9d3e7b2
Revises: 65e35a9cd981
Create Date: 2026-09-06 23:30:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'c1a4f9d3e7b2'
down_revision: Union[str, Sequence[str], None] = '65e35a9cd981'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS trusted_channels (
            trusted_channel_id  BIGSERIAL PRIMARY KEY,
            username            TEXT NOT NULL UNIQUE,
            category            TEXT,
            display_name        TEXT
        )
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS subscriptions (
            subscription_id     BIGSERIAL PRIMARY KEY,
            user_id             BIGINT NOT NULL,
            chat_id             BIGINT NOT NULL,
            channel_name        TEXT,
            username            TEXT,
            about               TEXT,
            trusted_channel_id  BIGINT REFERENCES trusted_channels(trusted_channel_id),
            detected_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
            UNIQUE (user_id, chat_id)
        )
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS messages (
            msg_id       BIGSERIAL PRIMARY KEY,
            tg_msg_id    BIGINT NOT NULL,
            user_id      BIGINT NOT NULL,
            chat_id      BIGINT NOT NULL,
            chat_name    TEXT,
            chat_type    TEXT,
            datetime     TIMESTAMPTZ NOT NULL,
            text         TEXT NOT NULL,
            is_forward   BOOLEAN NOT NULL DEFAULT FALSE,
            is_reply     BOOLEAN NOT NULL DEFAULT FALSE,
            UNIQUE (chat_id, tg_msg_id)
        )
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS parse_state (
            user_id         BIGINT NOT NULL,
            chat_id         BIGINT NOT NULL,
            last_parsed_at  TIMESTAMPTZ,
            status          TEXT,
            error_message   TEXT,
            PRIMARY KEY (user_id, chat_id)
        )
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS ai_queue (
            queue_id       BIGSERIAL PRIMARY KEY,
            user_id        BIGINT NOT NULL,
            status         TEXT NOT NULL DEFAULT 'pending',
            created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
            processed_at   TIMESTAMPTZ,
            error_message  TEXT
        )
        """
    )

    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_ai_queue_status ON ai_queue (status)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_messages_user ON messages (user_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_subscriptions_user ON subscriptions (user_id)"
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DROP TABLE IF EXISTS ai_queue")
    op.execute("DROP TABLE IF EXISTS parse_state")
    op.execute("DROP TABLE IF EXISTS messages")
    op.execute("DROP TABLE IF EXISTS subscriptions")
    op.execute("DROP TABLE IF EXISTS trusted_channels")

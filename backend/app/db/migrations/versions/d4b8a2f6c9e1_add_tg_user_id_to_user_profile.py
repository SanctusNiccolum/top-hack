"""add tg_user_id to user_profile

Связка между внутренним user_profile.user_id (назначается при регистрации
по телефону) и реальным numeric Telegram ID, который парсер использует как
ключ в своих таблицах (messages/subscriptions/parse_state). Заполняется в
/telegram/login/* после успешной авторизации в Telegram.

Revision ID: d4b8a2f6c9e1
Revises: c1a4f9d3e7b2
Create Date: 2026-09-06 23:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd4b8a2f6c9e1'
down_revision: Union[str, Sequence[str], None] = 'c1a4f9d3e7b2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'user_profile',
        sa.Column('tg_user_id', sa.BigInteger(), nullable=True),
    )
    op.create_unique_constraint(
        'uq_user_profile_tg_user_id',
        'user_profile',
        ['tg_user_id'],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(
        'uq_user_profile_tg_user_id',
        'user_profile',
        type_='unique',
    )
    op.drop_column('user_profile', 'tg_user_id')

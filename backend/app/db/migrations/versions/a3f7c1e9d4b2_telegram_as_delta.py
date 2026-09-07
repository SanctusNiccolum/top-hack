"""telegram branch becomes a delta

Telegram-ветка не даёт самостоятельной оценки платёжеспособности — она
корректирует её («часто пишете о проектах — +10 баллов»). Модуль tg-ai
так и возвращает: поправку −25..+25, а не балл 0..100. Поэтому поле
переименовано, и рядом появились риск с объяснением: риск считается
отдельно от дельты и не должен в ней растворяться.

Revision ID: a3f7c1e9d4b2
Revises: f1d6e8b3a2c7
Create Date: 2026-09-07 05:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a3f7c1e9d4b2'
down_revision: Union[str, Sequence[str], None] = 'f1d6e8b3a2c7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Переименование, а не drop+add: в поле могли остаться данные, и
    # старая семантика (0..100) от новой отличается только трактовкой.
    op.alter_column('report', 'telegram_score', new_column_name='telegram_delta')

    op.add_column(
        'report',
        sa.Column('telegram_risk', sa.String(length=30), nullable=True),
    )
    op.add_column(
        'report',
        sa.Column('telegram_comment', sa.Text(), nullable=True),
    )

    # Значения, записанные по старой шкале 0..100, как поправку читать
    # нельзя — обнуляем, ветка пересчитается заново.
    op.execute("UPDATE report SET telegram_delta = NULL")


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('report', 'telegram_comment')
    op.drop_column('report', 'telegram_risk')
    op.alter_column('report', 'telegram_delta', new_column_name='telegram_score')

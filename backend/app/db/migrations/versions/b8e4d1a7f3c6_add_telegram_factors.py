"""store telegram factor breakdown

Модуль tg-ai возвращает не только итоговую поправку, но и разбивку по
категориям: [{category, contribution, evidence_count}]. Без неё на экране
можно показать лишь одно число, а пользователю нужно понимать, ЧТО
именно повлияло на оценку — и что делать, чтобы её поднять.

Revision ID: b8e4d1a7f3c6
Revises: a3f7c1e9d4b2
Create Date: 2026-09-07 06:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b8e4d1a7f3c6'
down_revision: Union[str, Sequence[str], None] = 'a3f7c1e9d4b2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'report',
        sa.Column('telegram_factors', sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('report', 'telegram_factors')

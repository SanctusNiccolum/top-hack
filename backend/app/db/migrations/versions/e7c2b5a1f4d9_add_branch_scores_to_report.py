"""add branch scores to report

Отчёт складывается из трёх независимых веток (анкета / банковская
выписка / telegram), которые считаются в разное время разными
эндпоинтами. Храним каждую отдельно, а `score` становится их взвешенной
комбинацией (app/services/score_combination.py).

Revision ID: e7c2b5a1f4d9
Revises: d4b8a2f6c9e1
Create Date: 2026-09-07 01:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e7c2b5a1f4d9'
down_revision: Union[str, Sequence[str], None] = 'd4b8a2f6c9e1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'report',
        sa.Column('survey_score', sa.Numeric(5, 2), nullable=True),
    )
    op.add_column(
        'report',
        sa.Column('statement_score', sa.Numeric(5, 2), nullable=True),
    )
    op.add_column(
        'report',
        sa.Column('telegram_score', sa.Numeric(5, 2), nullable=True),
    )

    # Существующие отчёты считались только по анкете — переносим их
    # значение в соответствующую ветку, чтобы пересчёт не занизил итог.
    op.execute("UPDATE report SET survey_score = score WHERE survey_score IS NULL")


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('report', 'telegram_score')
    op.drop_column('report', 'statement_score')
    op.drop_column('report', 'survey_score')

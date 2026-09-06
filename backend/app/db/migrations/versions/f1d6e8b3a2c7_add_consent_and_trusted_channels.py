"""add consent table and seed trusted_channels

Согласие на обработку данных нужно уметь предъявить (кейс построен на
анализе личных данных «с согласия пользователя»), поэтому храним его
отдельной таблицей с историей: отзыв не удаляет запись, а проставляет
revoked_at.

Заодно наполняем trusted_channels — таблица создавалась пустой, из-за
чего сверка подписок ничего не давала.

Revision ID: f1d6e8b3a2c7
Revises: e7c2b5a1f4d9
Create Date: 2026-09-07 02:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f1d6e8b3a2c7'
down_revision: Union[str, Sequence[str], None] = 'e7c2b5a1f4d9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# username канала БЕЗ @ — сверка идёт по нему, а не по заголовку
# (заголовок владелец канала может менять как угодно).
TRUSTED_CHANNELS = [
    # Финансы и финансовая грамотность — положительный сигнал.
    ("centralbank_russia", "finance", "Банк России"),
    ("investfuture", "finance", "InvestFuture"),
    ("tinkoff_invest_official", "finance", "Т-Инвестиции"),
    ("bcs_express", "finance", "БКС Экспресс"),
    ("rbc_news", "finance", "РБК"),
    ("fingramota", "finance", "Финансовая грамотность"),
    ("dohod", "finance", "Дохо́дъ"),
    # Работа и карьера — признак занятости.
    ("hh_ru", "job", "hh.ru"),
    ("careerspace", "job", "Careerspace"),
    ("getmatch", "job", "getmatch"),
    ("it_jobs_rus", "job", "IT Jobs"),
    # Образование.
    ("stepik_org", "education", "Stepik"),
    ("netology_ru", "education", "Нетология"),
    ("skillbox", "education", "Skillbox"),
    # Гэмблинг и ставки — понижающий сигнал.
    ("betboom_official", "gambling", "BetBoom"),
    ("fonbet_official", "gambling", "Фонбет"),
    ("winline_bet", "gambling", "Winline"),
    ("1xbet_official", "gambling", "1xBet"),
    ("ligastavok", "gambling", "Лига Ставок"),
    ("casino_online_top", "gambling", "Онлайн-казино"),
    # Быстрые займы и МФО — понижающий сигнал.
    ("zaymer_official", "microloan", "Займер"),
    ("webbankir", "microloan", "Webbankir"),
    ("moneyman_ru", "microloan", "MoneyMan"),
    # Крипта — повышенный риск.
    ("forklog", "crypto", "ForkLog"),
    ("if_market_news", "crypto", "Крипто-новости"),
]


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'consent',
        sa.Column('consent_id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('consent_type', sa.String(length=40), nullable=False),
        sa.Column('granted_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('document_version', sa.String(length=40), nullable=True),
        sa.Column('source_ip', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['user_profile.user_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('consent_id'),
    )
    op.create_index(
        op.f('ix_consent_user_id'), 'consent', ['user_id'], unique=False
    )

    # trusted_channels создаётся миграцией c1a4f9d3e7b2 (схема парсера).
    # ON CONFLICT — чтобы повторный прогон не падал на уникальном username.
    for username, category, display_name in TRUSTED_CHANNELS:
        op.execute(
            sa.text(
                "INSERT INTO trusted_channels (username, category, display_name) "
                "VALUES (:u, :c, :d) ON CONFLICT (username) DO NOTHING"
            ).bindparams(u=username, c=category, d=display_name)
        )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute(
        sa.text(
            "DELETE FROM trusted_channels WHERE username = ANY(:names)"
        ).bindparams(names=[c[0] for c in TRUSTED_CHANNELS])
    )

    op.drop_index(op.f('ix_consent_user_id'), table_name='consent')
    op.drop_table('consent')

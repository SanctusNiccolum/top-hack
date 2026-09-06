from app.db.base import Base
from datetime import datetime
from sqlalchemy import BigInteger, DateTime, ForeignKey, Numeric, Text
from sqlalchemy.orm import Mapped, mapped_column


class ReportModel(Base):
    __tablename__ = "report"

    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey(
            "user_profile.user_id",
            ondelete="CASCADE",
        ),
        primary_key=True,
    )

    # Итоговый скор — взвешенная комбинация веток ниже
    # (см. app/services/score_combination.py).
    score: Mapped[float] = mapped_column(
        Numeric(5, 2),
        nullable=False,
    )

    # Скоры по каждой ветке отдельно, все в шкале 0..100. NULL = ветка
    # ещё не считалась (например, пользователь не загрузил выписку) —
    # такие ветки в комбинацию не входят, а их вес распределяется на
    # остальные.
    survey_score: Mapped[float | None] = mapped_column(
        Numeric(5, 2),
        nullable=True,
    )

    statement_score: Mapped[float | None] = mapped_column(
        Numeric(5, 2),
        nullable=True,
    )

    telegram_score: Mapped[float | None] = mapped_column(
        Numeric(5, 2),
        nullable=True,
    )

    date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    comment_from_ai: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
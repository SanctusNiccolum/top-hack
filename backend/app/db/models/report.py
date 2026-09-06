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

    score: Mapped[float] = mapped_column(
        Numeric(5, 2),
        nullable=False,
    )

    date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    comment_from_ai: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ConsentModel(Base):
    """Факт согласия пользователя на обработку данных.

    Кейс построен на анализе личных данных «с согласия пользователя», и
    согласие нужно уметь предъявить: кто, на что и когда согласился, с
    какого адреса. Отзыв не удаляет запись, а проставляет revoked_at —
    история согласий должна оставаться неизменной.
    """

    __tablename__ = "consent"

    consent_id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )

    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("user_profile.user_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # "telegram_analysis" | "bank_statement" | "personal_data"
    consent_type: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
    )

    granted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Текст, под которым пользователь подписался: формулировка со временем
    # меняется, а предъявлять нужно ту, что была показана в тот момент.
    document_version: Mapped[str | None] = mapped_column(
        String(40),
        nullable=True,
    )

    source_ip: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

from datetime import datetime
from decimal import Decimal
from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Numeric, Text, Integer, Float, TIMESTAMP, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
# from app.db.models.session import AccountSessionModel

class UserModel(Base):
    __tablename__ = 'user_profile'

    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)

    first_name: Mapped[str] = mapped_column(String(30), nullable=True)
    last_name: Mapped[str] = mapped_column(String(30), nullable=True)
    patronymic: Mapped[str] = mapped_column(String(30), nullable=True)

    phone_number: Mapped[str] = mapped_column(String(20), nullable=False)
    email: Mapped[str] = mapped_column(String(30), nullable=True)
    password: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )


    age: Mapped[int] = mapped_column(Integer, nullable=True)
    city: Mapped[str] = mapped_column(String(30), nullable=True)
    family_status: Mapped[str] = mapped_column(String(20), nullable=True)

    student_status: Mapped[str] = mapped_column(
        String(30),
        nullable=True,
    )

    student_course: Mapped[str] = mapped_column(
        String(30),
        nullable=True,
    )

    monthly_income: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=True,
    )

    self_employed: Mapped[bool] = mapped_column(
        Boolean,
        nullable=True,
    )

    income_frequency: Mapped[str] = mapped_column(
        String(30),
        nullable=True,
    )

    income_source: Mapped[str] = mapped_column(
        String(30),
        nullable=True,
    )

    income_source_other: Mapped[str] = mapped_column(
        String(255),
        nullable=True,
    )

    credit_history: Mapped[str] = mapped_column(
        String(30),
        nullable=True,
    )

    payment_overdue: Mapped[str] = mapped_column(
        String(30),
        nullable=True,
    )

    payment_method: Mapped[str] = mapped_column(
        String(30),
        nullable=True,
    )

    payment_method_other: Mapped[str] = mapped_column(
        String(255),
        nullable=True,
    )

    sessions: Mapped[list["AccountSessionModel"]] = relationship(
        "AccountSessionModel",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    subscriptions: Mapped[list["UserSubscriptionModel"]] = relationship(
        "UserSubscriptionModel",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    

    is_ended: Mapped[bool] = mapped_column(Boolean, default=False)


class UserSubscriptionModel(Base):
    __tablename__ = "user_subscription"

    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("user_profile.user_id", ondelete="CASCADE"),
        primary_key=True,
    )

    subscription_type: Mapped[str] = mapped_column(
        String(30),
        primary_key=True,
    )

    user: Mapped["UserModel"] = relationship(
        "UserModel",
        back_populates="subscriptions",
    )


class AccountSessionModel(Base):
    __tablename__ = "account_session"

    session_id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
    )

    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey(
            "user_profile.user_id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    token_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        unique=True,
        index=True,
    )

    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )

    revoked: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.now(),
    )

    user: Mapped["UserModel"] = relationship(
        "UserModel",
        back_populates="sessions",
    )
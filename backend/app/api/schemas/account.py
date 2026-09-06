from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.api.schemas.enums import (
    CreditHistory,
    FamilyStatus,
    IncomeFrequency,
    IncomeSource,
    PaymentMethod,
    PaymentOverdue,
    StudentCourse,
    StudentStatus,
    SubscriptionType,
)


class AccountUpdateRequest(BaseModel):
    first_name: str | None = Field(
        default=None,
        max_length=30,
    )

    last_name: str | None = Field(
        default=None,
        max_length=30,
    )

    patronymic: str | None = Field(
        default=None,
        max_length=30,
    )

    email: str | None = Field(
        default=None,
        max_length=255,
    )

    age: int | None = Field(
        default=None,
        ge=18,
        le=100,
    )

    city: str | None = Field(
        default=None,
        max_length=30,
    )

    family_status: FamilyStatus | None = None

    student_status: StudentStatus | None = None

    student_course: StudentCourse | None = None

    monthly_income: Decimal | None = Field(
        default=None,
        ge=0,
    )

    self_employed: bool | None = None

    income_frequency: IncomeFrequency | None = None

    income_source: IncomeSource | None = None

    income_source_other: str | None = Field(
        default=None,
        max_length=255,
    )

    credit_history: CreditHistory | None = None

    payment_overdue: PaymentOverdue | None = None

    payment_method: PaymentMethod | None = None

    payment_method_other: str | None = Field(
        default=None,
        max_length=255,
    )

    subscriptions: list[SubscriptionType] | None = None


class AccountResponse(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
    )

    user_id: int

    phone_number: str

    email: str | None

    first_name: str | None
    last_name: str | None
    patronymic: str | None

    age: int | None
    city: str | None

    family_status: FamilyStatus | None

    student_status: StudentStatus | None
    student_course: StudentCourse | None

    monthly_income: Decimal | None

    self_employed: bool | None

    income_frequency: IncomeFrequency | None

    income_source: IncomeSource | None
    income_source_other: str | None

    credit_history: CreditHistory | None

    payment_overdue: PaymentOverdue | None

    payment_method: PaymentMethod | None
    payment_method_other: str | None

    subscriptions: list[SubscriptionType]

    is_ended: bool
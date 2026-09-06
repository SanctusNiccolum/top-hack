from decimal import Decimal

from app.db.models.user import UserModel
from app.api.schemas.enums import (
    CreditHistory,
    FamilyStatus,
    IncomeFrequency,
    IncomeSource,
    PaymentMethod,
    PaymentOverdue,
    StudentStatus,
    SubscriptionType,
)


class ScoringService:

    @staticmethod
    def calculate_age_coefficient(
        age: int,
    ) -> Decimal:

        if age < 18:
            return Decimal("0")

        if 18 <= age <= 21:
            return Decimal("0.85")

        if 22 <= age <= 25:
            return Decimal("0.95")

        if 26 <= age <= 45:
            return Decimal("1.10")

        if 46 <= age <= 60:
            return Decimal("1.05")

        if 61 <= age <= 70:
            return Decimal("1.00")

        return Decimal("0.95")

    @staticmethod
    def calculate_family_coefficient(
        family_status: str,
    ) -> Decimal:

        coefficients = {
            FamilyStatus.MARRIED.value: Decimal("1.05"),
            FamilyStatus.CIVIL_MARRIAGE.value: Decimal("1.02"),
            FamilyStatus.SINGLE.value: Decimal("1.00"),
        }

        return coefficients.get(
            family_status,
            Decimal("1.00"),
        )

    @staticmethod
    def calculate_student_coefficient(
        student_status: str,
        student_course: str | None,
    ) -> Decimal:

        if student_status == StudentStatus.NOT_STUDENT.value:
            return Decimal("1.00")

        if student_status == StudentStatus.PART_TIME.value:
            return Decimal("0.90")

        if student_status != StudentStatus.FULL_TIME.value:
            return Decimal("1.00")

        coefficients = {
            "FIRST": Decimal("0.70"),
            "SECOND": Decimal("0.75"),
            "THIRD": Decimal("0.80"),
            "FOURTH": Decimal("0.85"),
            "FIFTH": Decimal("0.85"),
            "MASTER_OR_POSTGRADUATE": Decimal("0.90"),
        }

        return coefficients.get(
            student_course or "",
            Decimal("1.00"),
        )

    @staticmethod
    def calculate_subscription_coefficient(
        subscriptions: list[str],
    ) -> Decimal:

        if not subscriptions:
            return Decimal("1.00")

        coefficients = {
            SubscriptionType.ENTERTAINMENT.value: Decimal("0.98"),
            SubscriptionType.EDUCATION.value: Decimal("1.05"),
            SubscriptionType.SOFTWARE.value: Decimal("1.05"),
            SubscriptionType.FITNESS.value: Decimal("1.02"),
            SubscriptionType.NONE.value: Decimal("1.00"),
            SubscriptionType.UNKNOWN.value: Decimal("0.97"),
        }

        selected_coefficients = [
            coefficients.get(
                subscription,
                Decimal("1.00"),
            )
            for subscription in subscriptions
        ]

        return sum(
            selected_coefficients,
            Decimal("0"),
        ) / Decimal(len(selected_coefficients))

    @staticmethod
    def calculate_income_source_coefficient(
        income_source: str,
    ) -> Decimal:

        coefficients = {
            IncomeSource.EMPLOYMENT.value: Decimal("1.10"),
            IncomeSource.SELF_EMPLOYED.value: Decimal("1.00"),
            IncomeSource.SCHOLARSHIP.value: Decimal("0.85"),
            IncomeSource.PENSION.value: Decimal("1.05"),
            IncomeSource.OTHER.value: Decimal("0.90"),
        }

        return coefficients.get(
            income_source,
            Decimal("1.00"),
        )

    @staticmethod
    def calculate_npd_coefficient(
        npd_certificate_attached: bool,
    ) -> Decimal:

        if npd_certificate_attached:
            return Decimal("1.00")

        return Decimal("0.90")

    @staticmethod
    def calculate_income_frequency_coefficient(
        income_frequency: str,
    ) -> Decimal:

        coefficients = {
            IncomeFrequency.WEEKLY.value: Decimal("1.08"),
            IncomeFrequency.ONE_TWO_TIMES_MONTH.value: Decimal("1.10"),
            IncomeFrequency.EVERY_TWO_THREE_MONTHS.value: Decimal("0.90"),
            IncomeFrequency.IRREGULAR.value: Decimal("0.80"),
            IncomeFrequency.NONE.value: Decimal("0.50"),
        }

        return coefficients.get(
            income_frequency,
            Decimal("1.00"),
        )

    @staticmethod
    def calculate_credit_history_coefficient(
        credit_history: list[str],
    ) -> Decimal:

        if not credit_history:
            return Decimal("1.00")

        # МФО имеет приоритет над остальными вариантами.
        if CreditHistory.MICROLOAN.value in credit_history:
            return Decimal("0.80")

        coefficients = {
            CreditHistory.BANK_CREDIT.value: Decimal("1.05"),
            CreditHistory.STUDENT_CREDIT.value: Decimal("1.02"),
            CreditHistory.INSTALLMENT.value: Decimal("0.99"),
            CreditHistory.NONE.value: Decimal("0.95"),
        }

        selected_coefficients = [
            coefficients.get(
                item,
                Decimal("1.00"),
            )
            for item in credit_history
        ]

        return sum(
            selected_coefficients,
            Decimal("0"),
        ) / Decimal(len(selected_coefficients))

    @staticmethod
    def calculate_overdue_coefficient(
        payment_overdue: str,
    ) -> Decimal:

        coefficients = {
            PaymentOverdue.YES.value: Decimal("0.65"),
            PaymentOverdue.NO.value: Decimal("1.20"),
            PaymentOverdue.UNKNOWN.value: Decimal("0.90"),
        }

        return coefficients.get(
            payment_overdue,
            Decimal("1.00"),
        )

    @staticmethod
    def calculate_payment_method_coefficient(
        payment_methods: list[str],
    ) -> Decimal:

        if not payment_methods:
            return Decimal("1.00")

        coefficients = {
            PaymentMethod.CASH.value: Decimal("0.97"),
            PaymentMethod.BANK_CARD.value: Decimal("1.03"),
            PaymentMethod.SBP.value: Decimal("1.02"),
            PaymentMethod.CRYPTO.value: Decimal("0.95"),
            PaymentMethod.OTHER.value: Decimal("1.00"),
        }

        selected_coefficients = [
            coefficients.get(
                method,
                Decimal("1.00"),
            )
            for method in payment_methods
        ]

        return sum(
            selected_coefficients,
            Decimal("0"),
        ) / Decimal(len(selected_coefficients))

    @classmethod
    def calculate(
        cls,
        user: UserModel,
        subscriptions: list[str],
        monthly_payments: Decimal,
        npd_certificate_attached: bool,
    ) -> Decimal:

        # =========================
        # 1. Gate по возрасту
        # =========================

        if user.age is None:
            raise ValueError(
                "Не указан возраст"
            )

        if user.age < 18:
            return Decimal("0.00")

        # =========================
        # 2. Проверяем доход
        # =========================

        if user.monthly_income is None:
            raise ValueError(
                "Не указан ежемесячный доход"
            )

        if user.monthly_income <= 0:
            return Decimal("0.00")

        # =========================
        # 3. ПДН
        # =========================

        pdn = (
            monthly_payments
            / user.monthly_income
            * Decimal("100")
        )

        base_score = (
            Decimal("100") - pdn
        )

        # =========================
        # 4. Коэффициенты
        # =========================

        coefficients = []

        # Блок 1
        coefficients.append(
            cls.calculate_age_coefficient(
                user.age
            )
        )

        if user.family_status is not None:
            coefficients.append(
                cls.calculate_family_coefficient(
                    user.family_status
                )
            )

        if user.student_status is not None:
            coefficients.append(
                cls.calculate_student_coefficient(
                    user.student_status,
                    user.student_course,
                )
            )

        coefficients.append(
            cls.calculate_subscription_coefficient(
                subscriptions
            )
        )

        # Блок 2
        if user.income_source is not None:
            coefficients.append(
                cls.calculate_income_source_coefficient(
                    user.income_source
                )
            )

        coefficients.append(
            cls.calculate_npd_coefficient(
                npd_certificate_attached
            )
        )

        if user.income_frequency is not None:
            coefficients.append(
                cls.calculate_income_frequency_coefficient(
                    user.income_frequency
                )
            )

        # Блок 3
        if user.credit_history is not None:
            coefficients.append(
                cls.calculate_credit_history_coefficient(
                    [user.credit_history]
                )
            )

        if user.payment_overdue is not None:
            coefficients.append(
                cls.calculate_overdue_coefficient(
                    user.payment_overdue
                )
            )

        if user.payment_method is not None:
            coefficients.append(
                cls.calculate_payment_method_coefficient(
                    [user.payment_method]
                )
            )

        # =========================
        # 5. K_итог
        # =========================

        total_coefficient = Decimal("1.00")

        for coefficient in coefficients:
            total_coefficient *= coefficient

        # =========================
        # 6. Итоговый score
        # =========================

        score = (
            base_score
            * total_coefficient
        )

        # =========================
        # 7. Ограничение 0...100
        # =========================

        score = max(
            Decimal("0"),
            min(
                Decimal("100"),
                score,
            ),
        )

        return score.quantize(
            Decimal("0.01")
        )
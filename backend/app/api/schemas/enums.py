from enum import StrEnum


class FamilyStatus(StrEnum):
    MARRIED = "MARRIED"
    CIVIL_MARRIAGE = "CIVIL_MARRIAGE"
    SINGLE = "SINGLE"


class StudentStatus(StrEnum):
    FULL_TIME = "FULL_TIME"
    PART_TIME = "PART_TIME"
    NOT_STUDENT = "NOT_STUDENT"


class StudentCourse(StrEnum):
    FIRST = "FIRST"
    SECOND = "SECOND"
    THIRD = "THIRD"
    FOURTH = "FOURTH"
    FIFTH = "FIFTH"
    MASTER_OR_POSTGRADUATE = "MASTER_OR_POSTGRADUATE"


class IncomeSource(StrEnum):
    EMPLOYMENT = "EMPLOYMENT"
    SELF_EMPLOYED = "SELF_EMPLOYED"
    SCHOLARSHIP = "SCHOLARSHIP"
    PENSION = "PENSION"
    NONE = "NONE"
    OTHER = "OTHER"


class IncomeFrequency(StrEnum):
    WEEKLY = "WEEKLY"
    ONE_TWO_TIMES_MONTH = "ONE_TWO_TIMES_MONTH"
    EVERY_TWO_THREE_MONTHS = "EVERY_TWO_THREE_MONTHS"
    IRREGULAR = "IRREGULAR"
    NONE = "NONE"


class CreditHistory(StrEnum):
    BANK_CREDIT = "BANK_CREDIT"
    STUDENT_CREDIT = "STUDENT_CREDIT"
    MICROLOAN = "MICROLOAN"
    INSTALLMENT = "INSTALLMENT"
    NONE = "NONE"


class PaymentOverdue(StrEnum):
    YES = "YES"
    NO = "NO"
    UNKNOWN = "UNKNOWN"


class PaymentMethod(StrEnum):
    CASH = "CASH"
    BANK_CARD = "BANK_CARD"
    SBP = "SBP"
    CRYPTO = "CRYPTO"
    OTHER = "OTHER"


class SubscriptionType(StrEnum):
    ENTERTAINMENT = "ENTERTAINMENT"
    EDUCATION = "EDUCATION"
    SOFTWARE = "SOFTWARE"
    FITNESS = "FITNESS"
    NONE = "NONE"
    UNKNOWN = "UNKNOWN"
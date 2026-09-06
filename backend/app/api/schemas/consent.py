from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ConsentGrantRequest(BaseModel):
    # "telegram_analysis" | "bank_statement" | "personal_data"
    consent_type: str = Field(max_length=40)

    # Версия текста согласия, который был показан пользователю.
    document_version: str | None = Field(
        default=None,
        max_length=40,
    )


class ConsentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    consent_id: int
    consent_type: str
    granted_at: datetime
    revoked_at: datetime | None
    document_version: str | None

from decimal import Decimal

from pydantic import BaseModel


class StatementUploadResponse(BaseModel):
    # Скор именно по выписке, приведённый к общей шкале 0..100.
    statement_score: Decimal
    # Он же в «родной» шкале модуля (0..25) — для сверки с их отчётом.
    statement_score_raw: Decimal
    ai_comment: str
    stored_file: str

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.account import router as account_router
from app.api.auth import router as auth_router
from app.api.consent import router as consent_router
from app.api.report import router as report_router
from app.statement_scoring.router import router as statement_scoring_router
from app.telegram_analysis.router import router as telegram_analysis_router


app = FastAPI()


# Без этого браузер режет ЛЮБОЙ запрос с фронта: он живёт на своём порту
# (Vite), а API — на другом, это разные origin. Для хакатона список
# разрешённых origin'ов открытый; для прода его надо сузить.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(account_router)
app.include_router(auth_router)
app.include_router(report_router)
app.include_router(telegram_analysis_router)
app.include_router(statement_scoring_router)
app.include_router(consent_router)
from fastapi import FastAPI

from app.api.account import router as account_router
from app.api.auth import router as auth_router
from app.api.report import router as report_router


app = FastAPI()


app.include_router(account_router)
app.include_router(auth_router)
app.include_router(report_router)
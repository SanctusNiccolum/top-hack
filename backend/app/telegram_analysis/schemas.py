from pydantic import BaseModel, Field


class TelegramAnalyzeRequest(BaseModel):
    # Клиент получает session_string за пределами этого сервиса (полноценный
    # login-flow phone/code/password ещё не реализован — см. telegram_parser/dev_tools/get_session.py
    # для ручного получения строки сессии на время разработки).
    session_string: str
    chat_ids: list[int] = Field(min_length=1)


class TelegramAnalyzeResponse(BaseModel):
    status: str


class TelegramLoginPhoneRequest(BaseModel):
    phone_number: str


class TelegramLoginPhoneResponse(BaseModel):
    login_id: str


class TelegramLoginCodeRequest(BaseModel):
    login_id: str
    code: str


class TelegramLoginPasswordRequest(BaseModel):
    login_id: str
    password: str


class TelegramLoginResult(BaseModel):
    # "ok" | "need_password"
    status: str
    session_string: str | None = None
    telegram_user_id: int | None = None


class TelegramChatsRequest(BaseModel):
    session_string: str


class TelegramChat(BaseModel):
    chat_id: int
    name: str | None
    username: str | None
    # "own_messages" | "subscription"
    type: str


class TelegramChatsResponse(BaseModel):
    chats: list[TelegramChat]

"""Fake stand-in for the real `telethon` package, used only to exercise
telegram_parser's own logic (main.py / telegram_client.py) without a real
Telegram account or network access.
"""
from .errors import FloodWaitError  # noqa: F401 (re-exported for parity)

# Test scenario storage — populated by the test harness before each run,
# read by the fake client's methods below.
SCENARIO = {
    "authorized": True,
    "me_id": 999,
    "entities": {},       # chat_id -> entity-like object
    "messages": {},       # chat_id -> list[_Msg], newest-first
    "about": {},          # chat_id -> str|None, for GetFullChannelRequest
    "no_full_channel": {},  # chat_id -> True to force GetFullChannelRequest to raise
    "flood": {},           # chat_id -> {"seconds": int, "times": int} remaining flood-waits
    "raise_on_entity": {},  # chat_id -> Exception to raise from get_entity
    "get_dialogs_calls": 0,  # incremented each time get_dialogs() is called
}


class Entity:
    def __init__(self, chat_id, title=None, first_name=None, username=None):
        self._chat_id = chat_id
        self.title = title
        self.first_name = first_name
        self.username = username


class Msg:
    def __init__(self, id, date, sender_id, raw_text, forward=None, reply_to=None):
        self.id = id
        self.date = date
        self.sender_id = sender_id
        self.raw_text = raw_text
        self.forward = forward
        self.reply_to = reply_to


class _FullChat:
    def __init__(self, about):
        self.about = about


class _FullChannelResponse:
    def __init__(self, about):
        self.full_chat = _FullChat(about)


class TelegramClient:
    def __init__(self, session, api_id, api_hash):
        self.session = session
        self.api_id = api_id
        self.api_hash = api_hash
        self.logged_out = False
        self.disconnected = False

    async def connect(self):
        return True

    async def is_user_authorized(self):
        return SCENARIO["authorized"]

    async def get_me(self):
        class Me:
            id = SCENARIO["me_id"]
        return Me()

    async def get_dialogs(self):
        # Real Telethon populates its entity cache as a side effect of this
        # call — this fake doesn't need the cache (get_entity below reads
        # straight from SCENARIO), it just needs to exist and be callable
        # so main.py's warm-up call doesn't blow up, and to prove it was
        # actually called (see test_get_dialogs_is_called_before_parsing).
        SCENARIO["get_dialogs_calls"] += 1
        return []

    async def get_entity(self, chat_id):
        if chat_id in SCENARIO["raise_on_entity"]:
            raise SCENARIO["raise_on_entity"][chat_id]
        return SCENARIO["entities"][chat_id]

    async def iter_messages(self, chat_id, **kwargs):
        flood = SCENARIO["flood"].get(chat_id)
        if flood and flood["times"] > 0:
            flood["times"] -= 1
            raise FloodWaitError(seconds=flood["seconds"])
        for m in SCENARIO["messages"].get(chat_id, []):
            yield m

    async def __call__(self, request):
        chat_id = request.channel._chat_id
        if SCENARIO["no_full_channel"].get(chat_id):
            raise Exception("CHANNEL_PRIVATE or not a channel")
        return _FullChannelResponse(SCENARIO["about"].get(chat_id))

    async def log_out(self):
        self.logged_out = True

    async def disconnect(self):
        self.disconnected = True

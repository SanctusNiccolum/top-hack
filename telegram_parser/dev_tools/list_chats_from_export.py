"""ТЕСТОВЫЙ dev-инструмент — не часть парсера и не для прода.

Показывает список чатов внутри вашего экспортированного result.json —
чтобы найти chat_id для JSON-входа main_import.py, не читая файл руками.
Никакого обращения к Telegram, только чтение локального файла.

Запуск:
    python dev_tools/list_chats_from_export.py /path/to/result.json
"""
import json
import sys

sys.path.insert(0, __file__.rsplit("/", 2)[0])
from telegram_parser.import_parser import classify_chat_type  # noqa: E402


def main() -> None:
    if len(sys.argv) != 2:
        print("Использование: python list_chats_from_export.py /path/to/result.json")
        return

    with open(sys.argv[1], encoding="utf-8") as f:
        export = json.load(f)

    owner = export.get("personal_information", {})
    print(f"Аккаунт: {owner.get('first_name', '')} {owner.get('last_name', '')} "
          f"(user_id={owner.get('user_id')})\n")

    print(f"{'chat_id':>14}  {'наш type':<14}  {'сообщений':>10}  название (тип в экспорте)")
    print("-" * 90)
    for chat in export.get("chats", {}).get("list", []):
        our_type = classify_chat_type(chat.get("type", ""))
        n_messages = len(chat.get("messages", []))
        print(f"{chat['id']:>14}  {our_type:<14}  {n_messages:>10}  "
              f"{chat.get('name') or '(без названия)'} ({chat.get('type')})")


if __name__ == "__main__":
    main()

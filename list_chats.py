import os
from telethon import TelegramClient
from dotenv import load_dotenv
load_dotenv()

API_ID = int(os.getenv("TELEGRAM_API_ID", "0"))
API_HASH = os.getenv("TELEGRAM_API_HASH", "")
SESSION_NAME = "tg_promos_session"

client = TelegramClient(SESSION_NAME, API_ID, API_HASH)

async def main():
    print("Nome | @username | id")
    async for d in client.iter_dialogs():
        name = d.name
        ent = d.entity
        uname = getattr(ent, 'username', None)
        cid = getattr(ent, 'id', None)
        print(f"- {name} | @{uname} | {cid}")

with client:
    client.loop.run_until_complete(main())

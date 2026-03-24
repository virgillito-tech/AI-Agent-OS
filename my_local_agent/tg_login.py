# tg_login.py
import os
from telethon.sync import TelegramClient
import config # Assicurati di aver messo TG_API_ID e TG_API_HASH in config.py

session_path = os.path.join("sandbox", "tg_personal_session")

print("🤖 Avvio login Telegram Personale dell'Agente...")
client = TelegramClient(session_path, config.TG_API_ID, config.TG_API_HASH)

with client:
    print("✅ Login Telegram effettuato con successo! Sessione salvata.")
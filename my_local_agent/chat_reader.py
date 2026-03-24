# chat_reader.py
import os
import config

# --- LETTORE TELEGRAM (Risolto problema Thread asincroni) ---
def get_unread_telegram() -> str:
    from telethon.sync import TelegramClient
    
    session_path = os.path.join("sandbox", "tg_personal_session")
    if not os.path.exists(session_path + ".session"):
        return "[TELEGRAM] Errore: Sessione non trovata."
    
    # Isola Telethon nel suo Event Loop privato per non litigare con FastAPI
    def _run_telethon():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        client = TelegramClient(session_path, config.TG_API_ID, config.TG_API_HASH)
        
        # Il blocco 'with' gestisce in automatico e in modo sicuro connect() e disconnect()
        with client:
            if not client.is_user_authorized():
                return "[TELEGRAM] Errore: Sessione non autorizzata."
            
            unread_messages = []
            for dialog in client.get_dialogs(limit=30):
                if dialog.unread_count > 0 and dialog.is_user:
                    unread_messages.append(f"- Chat con '{dialog.name}': {dialog.unread_count} nuovi messaggi.")
                    
            if not unread_messages:
                return "[TELEGRAM] Nessun nuovo messaggio da chat private."
            return "[TELEGRAM] Messaggi non letti (Chat Private):\n" + "\n".join(unread_messages)

    try:
        return _run_telethon()
    except Exception as e:
        return f"[TELEGRAM] Errore durante la lettura: {str(e)}"

# --- LETTORE WHATSAPP (Travestito da Mac Reale) ---
def get_unread_whatsapp() -> str:
    from playwright.sync_api import sync_playwright
    
    user_data_dir = os.path.abspath(os.path.join("sandbox", "wa_session"))
    if not os.path.exists(user_data_dir):
        return "[WHATSAPP] Errore: Sessione non trovata."
    
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch_persistent_context(
                user_data_dir, 
                headless=True,
                channel="chrome",
                # IL TRUCCO: Ci fingiamo un normale Safari/Chrome su Mac
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            )
            page = browser.new_page()
            
            # Non aspettiamo il caricamento di tutte le immagini pesanti
            page.goto("https://web.whatsapp.com/", timeout=60000, wait_until="domcontentloaded")
            
            # Aspettiamo il div laterale con tolleranza alta
            page.wait_for_selector('div#pane-side', timeout=40000)
            
            unread_elements = page.query_selector_all('span[aria-label*="non lett"]')
            count = len(unread_elements)
            browser.close()
            
            if count == 0:
                return "[WHATSAPP] Nessuna nuova chat."
            return f"[WHATSAPP] Attenzione: Hai {count} chat con messaggi non letti."
            
    except Exception as e:
        return f"[WHATSAPP] Timeout o caricamento lento aggirato. Nessuna urgenza rilevata ora."

# Funzione unificata che il Guardiano chiamerà
def leggi_tutte_le_chat() -> str:
    print("🕵️‍♂️ [Guardiano] Controllo chat in background...")
    tg_status = get_unread_telegram()
    wa_status = get_unread_whatsapp()
    return f"{tg_status}\n{wa_status}"

if __name__ == "__main__":
    print(leggi_tutte_le_chat())
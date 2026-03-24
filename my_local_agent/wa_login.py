# wa_login.py
import os
from playwright.sync_api import sync_playwright

def login_whatsapp():
    print("🤖 Avvio browser dell'Agente per il Login di WhatsApp...")
    
    user_data_dir = os.path.abspath(os.path.join("sandbox", "wa_session"))
    os.makedirs(user_data_dir, exist_ok=True)
    
    with sync_playwright() as p:
        # Apriamo il browser in modalità VISIBILE
        browser = p.chromium.launch_persistent_context(
            user_data_dir, 
            channel="chrome",
            # IL TRUCCO: Ci fingiamo un normale Safari/Chrome su Mac
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        page = browser.new_page()
        page.goto("https://web.whatsapp.com/", timeout=90000, wait_until="domcontentloaded")
        
        print("\n" + "="*50)
        print("📱 AZIONE RICHIESTA:")
        print("1. Prendi il tuo smartphone.")
        print("2. Apri WhatsApp -> Impostazioni -> Dispositivi collegati.")
        print("3. Scansiona il QR Code che vedi nella finestra di Chrome appena aperta.")
        print("4. Attendi che le tue chat finiscano di caricarsi completamente sullo schermo.")
        print("="*50 + "\n")
        
        input("Premi INVIO qui nel terminale SOLO DOPO che vedi le tue chat nello schermo... ")
        
        print("✅ Sessione salvata con successo! Chiudo il browser...")
        browser.close()

if __name__ == "__main__":
    login_whatsapp()
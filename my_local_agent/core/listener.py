# core/listener.py
import os
from pynput import keyboard
import asyncio
import httpx
from PIL import ImageGrab

# Su Mac è Cmd + Shift + I, su Windows/Linux è Win + Shift + I
COMBINATION = {keyboard.Key.cmd, keyboard.Key.shift, keyboard.KeyCode.from_char('i')}
current_keys = set()

def scatta_screenshot_universale() -> str:
    """Cattura lo schermo in modo trasparente su Mac, Windows e Linux."""
    print("📸 [AMBIENT] Scatto screenshot dello schermo in corso...")
    os.makedirs("sandbox", exist_ok=True)
    path = os.path.join("sandbox", "ambient_view.png")
    
    try:
        # Pillow gestisce automaticamente le API grafiche del sistema operativo corrente
        screenshot = ImageGrab.grab(all_screens=True) # Cattura anche i multi-monitor
        screenshot.save(path, format="PNG")
        return path
    except Exception as e:
        import platform
        if platform.system().lower() == "linux":
            print(f"❌ [AMBIENT] Errore Screenshot su Linux: {e}. Se usi Wayland, Pillow potrebbe non essere supportato nativamente. Considera di passare a X11.")
        else:
            print(f"❌ [AMBIENT] Errore nello scatto fotografico nativo: {e}")
        return ""

async def invia_notifica_telegram(image_path: str):
    """Invia lo screenshot a Telegram per iniziare l'interazione."""
    if not image_path:
        return
        
    chat_id_path = os.path.join("sandbox", "tg_chat_id.txt")
    if not os.path.exists(chat_id_path):
        print("❌ [AMBIENT] Manca il Chat ID di Telegram.")
        return

    with open(chat_id_path, "r") as f:
        chat_id = f.read().strip()

    token = os.getenv("TELEGRAM_TOKEN")
    if not token:
        return

    url = f"https://api.telegram.org/bot{token}/sendPhoto"
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            with open(image_path, "rb") as photo:
                await client.post(
                    url, 
                    data={"chat_id": chat_id, "caption": "👀 *Ho catturato il tuo schermo.*\nCosa vuoi sapere o fare con questa schermata?", "parse_mode": "Markdown"},
                    files={"photo": photo}
                )
        print("✅ [AMBIENT] Immagine inviata su Telegram! In attesa di ordini.")
    except Exception as e:
        print(f"❌ [AMBIENT] Errore API Telegram: {e}")

def on_press(key):
    # Converte i caratteri maiuscoli/minuscoli per sicurezza
    if hasattr(key, 'char') and key.char:
        key = keyboard.KeyCode.from_char(key.char.lower())
        
    if key in COMBINATION:
        current_keys.add(key)
        if all(k in current_keys for k in COMBINATION):
            print("\n⚡ [AMBIENT] Hotkey rilevata! Attivazione occhio digitale multipiattaforma...")
            path = scatta_screenshot_universale()
            # Pynput gira in un thread separato, quindi avviamo un loop isolato
            asyncio.run(invia_notifica_telegram(path))

def on_release(key):
    if hasattr(key, 'char') and key.char:
        key = keyboard.KeyCode.from_char(key.char.lower())
    try:
        current_keys.remove(key)
    except KeyError:
        pass

def avvia_listener():
    """Accende il demone di ascolto della tastiera in background."""
    print("🎧 [AMBIENT] Listener universale attivato (Win/Cmd + Shift + I).")
    listener = keyboard.Listener(on_press=on_press, on_release=on_release)
    listener.start()
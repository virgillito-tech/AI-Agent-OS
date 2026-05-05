# tools/agent_tools.py
import os
# Spegniamo la telemetria PRIMA di importare le librerie
os.environ["ANONYMIZED_TELEMETRY"] = "false"
import re
import base64
import glob
import subprocess
import config
import requests
import urllib.parse
import webbrowser
import yagmail
import pyautogui
import mss
import time
import chat_reader 
from datetime import datetime, timedelta, timezone
from langchain_core.tools import tool
from bs4 import BeautifulSoup
from langchain_core.messages import HumanMessage
from core.memory_rag import add_memory, retrieve_memory
from tools.google_tools import leggi_ultime_email, invia_email_google, leggi_prossimi_eventi_calendario

from langchain_openai import ChatOpenAI
from pydantic import Field

from core.scheduler import scheduler

# --- FIX PYDANTIC V2 ---
class SafeBrowserLLM(ChatOpenAI):
    provider: str = Field(default="openai")
    tiktoken_model_name: str = Field(default="gpt-4o")
    def __setattr__(self, name, value):
        if name in ["ainvoke", "invoke"]:
            object.__setattr__(self, name, value)
        else:
            super().__setattr__(name, value)

os.makedirs("sandbox", exist_ok=True)

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    )
}

# Sicurezza: Se l'agente impazzisce con il mouse, porta fisicamente
# il tuo vero mouse in uno dei 4 angoli dello schermo per bloccarlo (Fail-Safe)
pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.5

@tool
def ottieni_data_ora_sistema() -> str:
    """
    Interroga l'orologio del sistema operativo. 
    Usa questo strumento per sapere con certezza assoluta che giorno, mese e anno è oggi.
    """
    now = datetime.now() 
    risposta = f"Data e ora esatta del sistema: {now.strftime('%A, %d %B %Y, %H:%M:%S')}"
    print(f"⏰ [TOOL: Orologio] Richiesta effettuata. Restituito: {risposta}")
    return risposta

# --- FUNZIONE DI SICUREZZA INTERNA ---
def _is_write_permitted(target_path: str) -> bool:
    """Controlla se il percorso di scrittura è permesso in base alle impostazioni utente."""
    if config.ALLOW_GLOBAL_WRITE:
        return True # L'utente ha sbloccato i permessi globali!
    
    # Altrimenti, verifica che il path finale sia STRETTAMENTE dentro la cartella 'sandbox'
    sandbox_abs = os.path.abspath("sandbox")
    target_abs = os.path.abspath(target_path)
    return os.path.commonpath([sandbox_abs, target_abs]) == sandbox_abs

# --- NUOVI TOOL DI LETTURA GLOBALE ---
@tool
def esplora_file_sistema(percorso: str = ".") -> str:
    """
    Elenca i file e le cartelle in una directory specifica del computer.
    Puoi usare percorsi assoluti (es. '/Users/nome/Desktop' o '~') per navigare nell'intero PC.
    """
    path_reale = os.path.expanduser(percorso)
    print(f"📂 [TOOL: File System] Esplorazione cartella: '{path_reale}'")
    try:
        if not os.path.exists(path_reale):
            return f"La cartella {path_reale} non esiste."
        elementi = os.listdir(path_reale)
        if not elementi:
            return f"La cartella {path_reale} è vuota."
        return f"Contenuto di {path_reale}:\n" + "\n".join(f"- {e}" for e in elementi)
    except Exception as e:
        return f"Errore di accesso alla cartella: {e}"

@tool
def ricerca_web_affidabile(query: str, solo_notizie_recenti: bool = False) -> str:
    """
    Esegue una ricerca su Internet.
    IMPOSTA 'solo_notizie_recenti=True' SE l'utente chiede "ultime novità", "notizie di oggi" o eventi recenti.
    Usa query brevi e concise.
    """
    print(f"\n🌐 [TOOL: Ricerca Web] Avvio ricerca per: '{query}' (Recenti: {solo_notizie_recenti})")
    try:
        from datetime import datetime
        
        # Iniettiamo silenziosamente il mese e l'anno corrente nella query per fregare la SEO dei vecchi articoli
        mese_anno_corrente = datetime.now().strftime('%B %Y') 
        query_arricchita = f"{query} {mese_anno_corrente}" if solo_notizie_recenti else query
        
        url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query_arricchita)}"
        
        # Aggiungiamo il filtro temporale di DuckDuckGo: df=m (ultimo mese)
        if solo_notizie_recenti:
            url += "&df=m"
            
        headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
        
        res = requests.get(url, headers=headers, timeout=(3.0, 7.0))
        res.raise_for_status()
        
        soup = BeautifulSoup(res.text, "html.parser")
        
        risultati_formattati = []
        for div in soup.find_all("div", class_="result__body", limit=6):
            titolo_tag = div.find("a", class_="result__a")
            snippet_tag = div.find("a", class_="result__snippet")
            
            if titolo_tag and snippet_tag:
                titolo = titolo_tag.text.strip()
                link = titolo_tag.get('href', 'Link non disponibile')
                if "uddg=" in link:
                    link = urllib.parse.unquote(link.split("uddg=")[1].split("&")[0])
                snippet = snippet_tag.text.strip()
                risultati_formattati.append(f"Titolo: {titolo}\nLink: {link}\nEstratto: {snippet}")
        
        if not risultati_formattati:
            return "Nessun risultato testuale trovato per questo periodo."
            
        final_text = "\n---\n".join(risultati_formattati)
        print(f"🌐 [TOOL: Ricerca Web] ✅ Trovati {len(risultati_formattati)} risultati.")
        return final_text
    except Exception as e:
        print(f"🌐 [TOOL: Ricerca Web] ❌ ERRORE DI RETE: {str(e)}")
        return f"Errore di rete durante la ricerca web: {str(e)}"
    

def _get_vision_llm():
    from langchain_ollama import ChatOllama
    return ChatOllama(model=config.VISION_MODEL_NAME, temperature=0)

# --- TOOL VISIONE ASYNC (PER TURBOQUANT) ---
async def process_image(prompt_text: str, base64_image: str) -> str:
    print(f"👁️ [TOOL: Visione] Analisi immagine con TurboQuant...")
    # Fondamentale l'await per attivare la cache compressa
    vision_llm = await get_llm(task_type="reasoning") 
    message = HumanMessage(content=[
        {"type": "text", "text": f"Analista visivo: {prompt_text}"},
        {"type": "image_url", "image_url": f"data:image/jpeg;base64,{base64_image}"},
    ])
    res = await vision_llm.ainvoke([message])
    return res.content

@tool
async def analyze_local_image(image_path: str, user_prompt: str = "") -> str:
    """Analizza immagini locali sfruttando TurboQuant."""
    try:
        with open(image_path, "rb") as f:
            img_b64 = base64.b64encode(f.read()).decode("utf-8")
        return await process_image(user_prompt, img_b64)
    except Exception as e: return f"Errore: {e}"

@tool
def save_memory(informazione: str) -> str:
    """
    Usa questo tool per memorizzare A LUNGO TERMINE informazioni importanti sull'utente.
    (Es. preferenze, nomi di familiari, date, acquisti, luoghi).
    Non usarlo per cose futili o per la storia della conversazione attuale.
    """
    print(f"💾 [TOOL: Memoria] Salvataggio: {informazione}")
    return add_memory(informazione)

@tool
def search_memory(query: str) -> str:
    """
    Usa questo tool per cercare informazioni nel passato o ricordi dell'utente.
    Se l'utente ti chiede "Ti ricordi come si chiama il mio cane?", usa questo tool con query="nome del cane".
    """
    print(f"🔍 [TOOL: Memoria] Ricerca per: {query}")
    return retrieve_memory(query)

@tool
def execute_python_code(code: str) -> str:
    """Esegue codice Python in una sandbox."""
    print(f"\n🐍 [TOOL: Python] Avvio esecuzione script...\n{code[:80]}...")
    try:
        script_path = os.path.join("sandbox", "temp_script.py")
        with open(script_path, "w", encoding="utf-8") as f: f.write(code)
        executable = "python" if os.name == "nt" else "python3"
        result = subprocess.run([executable, "temp_script.py"], cwd="sandbox", capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0:
            print(f"🐍 [TOOL: Python] ✅ Esecuzione completata. Output: {result.stdout[:80]}...")
            return f"Output: {result.stdout}"
        else:
            print(f"🐍 [TOOL: Python] ❌ Errore script: {result.stderr[:80]}...")
            return f"Errore script: {result.stderr}"
    except Exception as e: 
        print(f"🐍 [TOOL: Python] ❌ Fallimento critico: {str(e)}")
        return f"Fallimento critico: {str(e)}"

@tool
def apri_in_vscode(percorso: str) -> str:
    """Apre un file o cartella in VS Code."""
    print(f"💻 [TOOL: VS Code] Apertura di '{percorso}'...")
    try:
        subprocess.run(["code", percorso], check=True, capture_output=True, text=True)
        return f"Aperto '{percorso}' in VS Code."
    except FileNotFoundError:
        return "❌ Errore: Comando 'code' non trovato. Assicurati che Visual Studio Code sia installato e che sia stato aggiunto alle variabili d'ambiente (PATH) del tuo sistema operativo."
    except Exception as e: 
        return f"Errore durante l'apertura in VS Code: {e}"

@tool
def apri_sito_web_universale(url: str) -> str:
    """
    Apre un link nel browser PREDEFINITO DELL'UTENTE affinché L'UTENTE possa vederlo.
    ATTENZIONE: Tu (l'Agente) NON potrai leggere o interagire con questa pagina. 
    Usa questo tool SOLO se l'utente ti chiede esplicitamente di "aprire" o "mostrare" un sito per lui (es. "aprimi youtube").
    Se invece DEVI ESTRARRE INFORMAZIONI, fare ricerche o compiere azioni web, USA IL TOOL 'automazione_browser_ai'.
    """
    print(f"🌍 [TOOL: Browser] Apertura URL '{url}' sul monitor dell'utente...")
    try:
        webbrowser.open(url)
        return f"Ho aperto {url} nel browser dell'utente. Avvisalo che la pagina è aperta sul suo schermo."
    except Exception as e: return f"Errore: {e}"

@tool
def invia_email_universale(destinatario: str, oggetto: str, corpo: str) -> str:
    """Invia email SMTP tramite yagmail."""
    try:
        yag = yagmail.SMTP(user=os.getenv("EMAIL_USER"), password=os.getenv("EMAIL_PASSWORD"))
        yag.send(to=destinatario, subject=oggetto, contents=corpo)
        return f"Email inviata a {destinatario}."
    except Exception as e:
        return f"Errore invio email: {e}"

@tool
def genera_immagine_locale(prompt: str) -> str:
    """
    Genera un'immagine in LOCALE sfruttando la GPU (NVIDIA CUDA, Apple MPS o CPU), basata su un prompt.
    ATTENZIONE: Tu devi tradurre la richiesta dell'utente in un prompt in INGLESE estremamente dettagliato prima di eseguire.
    """
    print(f"\n🎨 [TOOL: Immagini] Avvio generazione per: '{prompt}'")
    try:
        import uuid
        import torch
        from diffusers import AutoPipelineForText2Image

        device = "cpu"
        dtype = torch.float32
        variant = None

        if torch.cuda.is_available():
            device = "cuda"
            dtype = torch.float16
            variant = "fp16"
            print("🎨 [TOOL: Immagini] Hardware rilevato: NVIDIA CUDA")
        elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            device = "mps"
            dtype = torch.float16
            variant = "fp16"
            print("🎨 [TOOL: Immagini] Hardware rilevato: Apple Silicon (MPS)")
        else:
            print("🎨 [TOOL: Immagini] Hardware rilevato: CPU (la generazione sarà lenta)")

        print("🎨 [TOOL: Immagini] Caricamento modello SDXL Base 1.0 nella VRAM...")
        
        pipe = AutoPipelineForText2Image.from_pretrained(
            "stabilityai/stable-diffusion-xl-base-1.0", 
            torch_dtype=dtype, 
            variant=variant,
            use_safetensors=True
        )
        pipe.to(device)

        print(f"🎨 [TOOL: Immagini] Rendering in corso su {device} (25 step)...")
        image = pipe(prompt=prompt, num_inference_steps=25).images[0]

        image_name = f"gen_img_{uuid.uuid4().hex[:8]}.png"
        image_path = os.path.join("sandbox", image_name)
        image.save(image_path)

        print(f"🎨 [TOOL: Immagini] ✅ Immagine salvata in: {image_path}")
        
        del pipe
        if device == "cuda":
            torch.cuda.empty_cache()
        elif device == "mps":
            torch.mps.empty_cache()

        return f"Immagine generata con altissima qualità. È stata salvata nella sandbox come '{image_name}'."

    except Exception as e:
        print(f"🎨 [TOOL: Immagini] ❌ Errore critico: {str(e)}")
        return f"Errore hardware/software durante la generazione dell'immagine: {e}"

@tool
def leggi_file_sistema(percorso_file: str) -> str:
    """
    Legge il contenuto testuale di qualsiasi file nel computer dell'utente.
    Usa percorsi assoluti completi (es. '~/Desktop/appunti.txt').
    """
    path_reale = os.path.expanduser(percorso_file)
    print(f"📖 [TOOL: File System] Lettura file globale: '{path_reale}'")
    try:
        with open(path_reale, "r", encoding="utf-8") as f:
            contenuto = f.read()
        return contenuto
    except Exception as e:
        return f"Impossibile leggere il file {path_reale}: {e}"
    
@tool
def scrivi_o_copia_file(percorso_destinazione: str, contenuto: str) -> str:
    """
    Crea, sovrascrive o copia un file. 
    Se non diversamente specificato, salva i file nella cartella 'sandbox/'.
    ATTENZIONE: Potresti non avere i permessi per scrivere fuori dalla sandbox. Se ricevi 'Permission Denied', avvisa l'utente.
    """
    path_reale = os.path.expanduser(percorso_destinazione)
    
    if not os.path.isabs(path_reale) and not path_reale.startswith("sandbox"):
        path_reale = os.path.join("sandbox", path_reale)
        
    print(f"\n💾 [TOOL: File System] Tentativo di scrittura in: '{path_reale}'")
    
    if not _is_write_permitted(path_reale):
        print(f"🛡️ [TOOL: Sicurezza] Scrittura bloccata! Permessi globali disattivati.")
        return "PERMISSION DENIED: Non hai l'autorizzazione per scrivere o modificare file fuori dalla cartella 'sandbox/'. Chiedi all'utente di abilitare i permessi globali dalle Impostazioni."

    try:
        os.makedirs(os.path.dirname(os.path.abspath(path_reale)), exist_ok=True)
        with open(path_reale, "w", encoding="utf-8") as f: 
            f.write(contenuto)
        print(f"💾 [TOOL: File System] ✅ Scrittura completata in {path_reale}")
        return f"File scritto con successo in: {path_reale}"
    except Exception as e: 
        return f"Errore critico durante la scrittura: {e}"

@tool
def gestisci_file_avanzato(azione: str, percorso_origine: str, percorso_destinazione: str = "") -> str:
    """
    Permette di gestire fisicamente i file e le cartelle sul computer.
    Azioni supportate: 
    - 'rinomina' o 'sposta': richiede 'percorso_origine' e 'percorso_destinazione'.
    - 'elimina': richiede solo 'percorso_origine' (ATTENZIONE: ELIMINAZIONE DEFINITIVA).
    """
    path_orig = os.path.expanduser(percorso_origine)
    path_dest = os.path.expanduser(percorso_destinazione) if percorso_destinazione else ""
    
    print(f"🔧 [TOOL: File System] Richiesta '{azione}' su: {path_orig}")
    
    if not _is_write_permitted(path_orig) or (path_dest and not _is_write_permitted(path_dest)):
        return "PERMISSION DENIED: Non hai l'autorizzazione per modificare o eliminare file fuori dalla Sandbox. L'utente deve attivare i permessi globali."
        
    try:
        if azione in ['rinomina', 'sposta']:
            if not path_dest: return "Errore: devi specificare il percorso di destinazione."
            os.rename(path_orig, path_dest)
            return f"✅ Successo: File spostato/rinominato da '{path_orig}' a '{path_dest}'"
            
        elif azione == 'elimina':
            if os.path.isfile(path_orig):
                os.remove(path_orig)
            else:
                import shutil
                shutil.rmtree(path_orig)
            return f"✅ Successo: Elemento '{path_orig}' eliminato fisicamente dal disco."
            
        else:
            return f"Azione '{azione}' non riconosciuta. Usa 'rinomina', 'sposta' o 'elimina'."
    except Exception as e:
        return f"Errore critico durante la modifica del file: {e}"

# --- TOOL WHATSAPP (SINTASSI CORRETTA) ---
@tool
async def leggi_whatsapp(nome_contatto: str) -> str:
    """Legge gli ultimi messaggi da una chat WhatsApp personale."""
    print(f"🟢 [TOOL: WhatsApp] Apertura chat: {nome_contatto}")
    try:
        from playwright.async_api import async_playwright
        user_data_dir = os.path.abspath(os.path.join("sandbox", "wa_session"))
        
        async with async_playwright() as p:
            browser = await p.chromium.launch_persistent_context(user_data_dir, headless=False)
            page = await browser.new_page()
            await page.goto("https://web.whatsapp.com/")
            await page.wait_for_selector('div[contenteditable="true"]', timeout=60000)
            
            # FIX: Rimosso await davanti all'assegnazione
            search_box = page.locator('div[contenteditable="true"][data-tab="3"]')
            await search_box.fill(nome_contatto)
            await asyncio.sleep(1)
            await page.keyboard.press("Enter")
            await asyncio.sleep(2) 
            
            # FIX: await va solo davanti alla funzione asincrona .all_inner_texts()
            messages = await page.locator('div.message-in, div.message-out').all_inner_texts()
            
            await browser.close()
            return "\n".join(messages[-5:]) if messages else "Nessun messaggio trovato."
    except Exception as e: return f"Errore WhatsApp: {str(e)}"

# --- TOOL TELEGRAM (NATIVO ASYNC - FIX DEFINITIVO) ---
@tool
async def leggi_telegram_personale(nome_contatto_o_username: str) -> str:
    """Legge i messaggi Telegram in modalità asincrona senza conflitti di loop."""
    from telethon import TelegramClient
    print(f"🔵 [TOOL: Telegram] Lettura chat: {nome_contatto_o_username}")
    session_path = os.path.join("sandbox", "tg_personal_session")
    
    # Usiamo il client asincrono correttamente dentro il loop esistente
    client = TelegramClient(session_path, config.TG_API_ID, config.TG_API_HASH)
    try:
        async with client: # Questo gestisce connessione e avvio automaticamente
            messages = await client.get_messages(nome_contatto_o_username, limit=5)
            if not messages: return "Nessun messaggio trovato."
            res = [f"{'Io' if m.out else nome_contatto_o_username}: {m.message}" for m in reversed(messages)]
            return "\n".join(res)
    except Exception as e:
        return f"Errore Telegram: {str(e)}"

@tool
def indicizza_cartella_personale(percorso_cartella: str) -> str:
    """
    Legge tutti i file di testo e PDF in una cartella e li salva nella memoria RAG (Database vettoriale locale).
    Usa questo tool se l'utente ti chiede di studiare, leggere o memorizzare i suoi appunti o documenti personali.
    """
    from core.document_rag import index_directory
    return index_directory(percorso_cartella)

@tool
def ricerca_nei_documenti_locali(query: str) -> str:
    """
    Cerca le informazioni nei documenti personali precedentemente indicizzati.
    Usa questo tool per rispondere a domande basandoti sui file locali dell'utente (es. bollette, appunti universitari, riassunti).
    """
    from core.document_rag import retrieve_document_context
    return retrieve_document_context(query)

@tool
async def scatta_e_analizza_schermo(domanda: str) -> str:
    """Scatta uno screenshot e lo analizza tramite TurboQuant."""
    try:
        with mss.mss() as sct:
            path = os.path.join("sandbox", "current_screen.png")
            sct.shot(output=path)
        with open(path, "rb") as f:
            img_base64 = base64.b64encode(f.read()).decode("utf-8")
        return await process_image(domanda, img_base64)
    except Exception as e: return f"Errore: {e}"

@tool
def esegui_azione_mouse_tastiera(azione: str, x: int = None, y: int = None, testo: str = None, tasto: str = None) -> str:
    """
    Esegue un'azione fisica con mouse o tastiera sul computer dell'utente.
    Azioni permesse: 'clic_sinistro', 'clic_destro', 'doppio_clic', 'sposta_mouse', 'scrivi_testo', 'premi_tasto'.
    Se l'azione richiede coordinate, fornisci x e y. Se richiede di scrivere, fornisci 'testo'. Se richiede un tasto speciale (es. 'enter', 'tab', 'command'), fornisci 'tasto'.
    """
    print(f"🖱️ [TOOL: GUI Automation] Esecuzione azione: {azione}...")
    try:
        if azione in ['clic_sinistro', 'clic_destro', 'doppio_clic', 'sposta_mouse']:
            if x is None or y is None:
                return "Errore: per le azioni del mouse devi fornire le coordinate X e Y."
            
            pyautogui.moveTo(x, y, duration=0.8)
            
            if azione == 'clic_sinistro':
                pyautogui.click()
            elif azione == 'clic_destro':
                pyautogui.rightClick()
            elif azione == 'doppio_clic':
                pyautogui.doubleClick()
            return f"Azione {azione} eseguita alle coordinate ({x}, {y})."
            
        elif azione == 'scrivi_testo':
            if not testo:
                return "Errore: devi fornire il parametro 'testo'."
            pyautogui.write(testo, interval=0.03)
            return f"Testo '{testo}' digitato con successo."
            
        elif azione == 'premi_tasto':
            if not tasto:
                return "Errore: devi fornire il parametro 'tasto'."
            pyautogui.press(tasto)
            return f"Tasto '{tasto}' premuto."
            
        else:
            return f"Azione '{azione}' non riconosciuta."
            
    except Exception as e:
        return f"Errore critico automazione GUI: {e}"

@tool
async def programma_task_autonomo(
    istruzione: str, 
    minuti_attesa: int = 0, 
    cron_minute: str = "", 
    cron_hour: str = "", 
    cron_day: str = "", 
    cron_month: str = "", 
    cron_day_of_week: str = "",
    cron_year: str = ""
) -> str:
    """
    Programma un task in cui TU STESSO (Agente) dovrai fare ricerche, analizzare dati o eseguire azioni nel futuro.
    - Per task singolo a breve termine: usa SOLO 'minuti_attesa' (es. 60 per tra un'ora).
    - Per TUTTI GLI ALTRI task ricorrenti (giornalieri, settimanali, mensili, annuali) o date esatte: compila i campi "cron_*" necessari.
      - cron_minute: "0-59"
      - cron_hour: "0-23"
      - cron_day: "1-31", oppure espressioni come "last" (ultimo giorno), "last sun" (ultima domenica)
      - cron_month: "1-12"
      - cron_day_of_week: "mon", "tue", "wed", "thu", "fri", "sat", "sun", oppure range come "mon-fri"
      - cron_year: anno a 4 cifre (es. "2026")
      Esempi: 
      - "Ogni giorno alle 09:00" -> cron_hour="9", cron_minute="0"
      - "Una volta a settimana il lunedì alle 7" -> cron_day_of_week="mon", cron_hour="7", cron_minute="0"
      - "Ogni ultima domenica del mese" -> cron_day="last sun", cron_hour="10", cron_minute="0"
      Lascia i campi vuoti ("") per ignorarli.
    L'istruzione deve descrivere ESATTAMENTE cosa dovrai fare.
    """
    print(f"📅 [TOOL: Scheduler] Richiesta autonomia: minuti={minuti_attesa}, cron={cron_hour}:{cron_minute} day={cron_day} dow={cron_day_of_week}")
    try:
        from core.scheduler import scheduler, _esegui_agente_in_background
        
        chat_id_path = os.path.join("sandbox", "tg_chat_id.txt")
        if not os.path.exists(chat_id_path):
            return "Errore: Manca il Chat ID di Telegram nella sandbox."
            
        with open(chat_id_path, "r") as f:
            chat_id = f.read().strip()

        if any([cron_minute, cron_hour, cron_day, cron_month, cron_day_of_week, cron_year]):
            cron_kwargs = {}
            if cron_minute: cron_kwargs['minute'] = cron_minute
            if cron_hour: cron_kwargs['hour'] = cron_hour
            if cron_day: cron_kwargs['day'] = cron_day
            if cron_month: cron_kwargs['month'] = cron_month
            if cron_day_of_week: cron_kwargs['day_of_week'] = cron_day_of_week
            if cron_year: cron_kwargs['year'] = cron_year
            
            try:
                scheduler.add_job(_esegui_agente_in_background, 'cron', args=[istruzione, chat_id], **cron_kwargs)
            except Exception as cron_err:
                return f"Errore di sintassi Cron: {cron_err}. Verifica i parametri e riprova."
                
            return f"✅ Task cron impostato con parametri: {cron_kwargs}. Istruzione: '{istruzione}'."
            
        elif minuti_attesa > 0:
            orario_locale_attuale = datetime.now(timezone.utc).astimezone()
            dt_obj = orario_locale_attuale + timedelta(minutes=minuti_attesa)
            scheduler.add_job(
                _esegui_agente_in_background, 'date', run_date=dt_obj, args=[istruzione, chat_id]
            )
            return f"✅ Task autonomo armato per le {dt_obj.strftime('%H:%M:%S')}."
            
        else: 
            return "Errore: specificare minuti_attesa o almeno un campo cron_*."
            
    except Exception as e: 
        return f"Errore critico nella pianificazione: {e}"

@tool
async def navigatore_web_integrato(istruzioni: str) -> str:
    """STRUMENTO UFFICIALE: Navigatore Web Nativo (Browser Use).
    Usa questo tool SOLO se devi compiere AZIONI COMPLESSE su un sito web (es. riempire un form, cliccare bottoni, navigare dentro un portale specifico).
    ATTENZIONE: Se devi solo cercare notizie, informazioni, risultati sportivi o meteo, USA IL TOOL 'ricerca_web_affidabile' CHE È MOLTO PIÙ VELOCE E SICURO.
    """
    print(f"🌐 [BROWSER AI] Avvio navigazione per: {istruzioni}")
    try:
        from browser_use import Agent
        import config

        engine = getattr(config, "ACTIVE_ENGINE", "ollama")
        url = getattr(config, "BASE_URL_TEXT", "http://localhost:11434").rstrip("/") + "/v1"

        # IL TRUCCO: Usiamo SEMPRE il modello Coder per guidare il browser!
        modello_pilota = "qwen2.5-coder:7b"
        
        print(f"🌐 [BROWSER AI] Affido il volante al modello specializzato: {modello_pilota}")

        llm_guida = SafeBrowserLLM(
            base_url=url,
            api_key="ollama", 
            model=modello_pilota,
            temperature=0.0, # Temperatura a zero per non fargli inventare nulla
        )

        browser_agent = Agent(task=istruzioni, llm=llm_guida)
        history = await browser_agent.run()

        risultato = history.final_result()
        if not risultato:
            return "Navigazione completata, ma nessun dato testuale restituito."

        print(f"🌐 [BROWSER AI] ✅ Navigazione completata.")
        return f"Risultato della navigazione web:\n{risultato}"

    except Exception as e:
        return f"Errore critico durante la navigazione: {str(e)}"
    

@tool
async def leggi_tutte_le_chat() -> str: # Diventa ASYNC
    """
    Legge in un colpo solo tutti i messaggi NON LETTI da Telegram e WhatsApp.
    Usa questo tool per avere un riepilogo rapido delle comunicazioni in sospeso dell'utente.
    """
    print("📱 [TOOL: Comunicazioni] Avvio lettura unificata chat...")
    # Eseguiamo la funzione in un executor per non bloccare il loop asincrono
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, chat_reader.leggi_tutte_le_chat)

@tool
def leggi_pagina_web(url: str) -> str:
    """
    Estrae e legge il puro contenuto testuale di qualsiasi pagina web (Wikipedia, articoli di news, blog).
    Usa questo tool quando devi LEGGERE informazioni da un sito specifico. È infallibile e velocissimo.
    Fornisci SOLO l'URL completo (es. 'https://it.wikipedia.org/wiki/Alan_Turing').
    """
    print(f"🕸️ [TOOL: Web Scraper] Estrazione testo da: {url}")
    try:
        import requests
        from bs4 import BeautifulSoup
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        }
        res = requests.get(url, headers=headers, timeout=10)
        res.raise_for_status()
        
        soup = BeautifulSoup(res.text, "html.parser")
        for element in soup(["script", "style", "nav", "footer", "header"]):
            element.decompose()
            
        paragrafi = soup.find_all(['p', 'h1', 'h2', 'h3'])
        testo_pulito = "\n\n".join([p.get_text(strip=True) for p in paragrafi if p.get_text(strip=True)])
        
        max_chars = 10000 
        if len(testo_pulito) > max_chars:
            testo_pulito = testo_pulito[:max_chars] + "\n\n...[TESTO TRONCATO]..."
            
        return f"Contenuto della pagina {url}:\n\n{testo_pulito}"
    except Exception as e:
        return f"Errore durante l'estrazione della pagina web: {str(e)}"

@tool
def crea_documento_pdf(titolo: str, contenuto: str, nome_file: str) -> str:
    """
    Crea un documento PDF formattato e lo salva sul computer.
    Usa questo tool per generare report, riassunti, articoli o fatture.
    Il 'nome_file' deve finire in .pdf (es. 'report_ai.pdf').
    """
    print(f"📄 [TOOL: Tipografo] Generazione PDF in corso: '{nome_file}'")
    try:
        from fpdf import FPDF
        import os
        
        if not nome_file.endswith(".pdf"):
            nome_file += ".pdf"
        path_reale = os.path.join("sandbox", nome_file)
        
        class PDF(FPDF):
            def header(self):
                self.set_font("helvetica", "B", 15)
                self.cell(0, 10, titolo, border=False, ln=True, align="C")
                self.ln(10)

            def footer(self):
                self.set_y(-15)
                self.set_font("helvetica", "I", 8)
                self.cell(0, 10, f"Generato dall'AI OS - Pagina {self.page_no()}", align="C")

        pdf = PDF()
        pdf.add_page()
        pdf.set_font("helvetica", size=11)
        
        contenuto_pulito = contenuto.encode('latin-1', 'replace').decode('latin-1')
        
        pdf.multi_cell(0, 8, txt=contenuto_pulito)
        pdf.output(path_reale)
        
        return f"✅ Documento PDF creato con successo e salvato in: {path_reale}"
    except Exception as e:
        return f"❌ Errore durante la creazione del PDF: {str(e)}"

@tool
def leggi_documento(file_path: str) -> str:
    """
    Usa questo tool per leggere ed estrarre il testo da file PDF, TXT, CSV, DOCX o Markdown.
    Passa come argomento il percorso assoluto del file (es. temp_uploads/nome_file.pdf).
    """
    print(f"📄 [TOOL: Lettore Documenti] Estrazione testo da: {file_path}")
    try:
        path_reale = os.path.expanduser(file_path)
        if not os.path.exists(path_reale):
            return f"Errore: Il file {path_reale} non esiste."
            
        estensione = os.path.splitext(path_reale)[1].lower()
        if estensione == '.pdf':
            try:
                import pypdf
            except ImportError:
                return "Errore: Libreria pypdf non installata. L'utente deve eseguire 'pip install pypdf'."
            
            testo_completo = ""
            with open(path_reale, "rb") as f:
                reader = pypdf.PdfReader(f)
                for i, page in enumerate(reader.pages):
                    if i > 50: break 
                    testo = page.extract_text()
                    if testo:
                        testo_completo += f"--- Pagina {i+1} ---\n{testo}\n\n"
            return testo_completo[:60000] 
        else:
            with open(path_reale, "r", encoding="utf-8") as f:
                return f.read()[:60000]
    except Exception as e:
        return f"Impossibile leggere il documento: {str(e)}"

# NOTA: _is_write_permitted rimosso per evitare crash di LangChain

@tool
def leggi_task_programmati() -> str:
    """
    Legge e restituisce l'elenco di tutti i task futuri (promemoria, ricerche automatiche, ecc.) programmati nel sistema.
    Usa ESCLUSIVAMENTE questo tool se l'utente ti chiede "quali task hai programmati?" o "ci sono appuntamenti in programma?".
    È SEVERAMENTE VIETATO usare la memoria a lungo termine (Qdrant) per i task futuri.
    """
    print("📅 [TOOL: Scheduler] Lettura dei task in programma SQLite...")
    try:
        from core.scheduler import scheduler
        jobs = scheduler.get_jobs()
        if not jobs:
            return "Non ci sono task o promemoria programmati al momento."
        
        lista_task = []
        for job in jobs:
            orario = job.next_run_time.strftime('%Y-%m-%d %H:%M:%S') if job.next_run_time else "In pausa"
            dettagli = job.args[0] if job.args else "Nessun dettaglio istruzione"
            lista_task.append(f"- ⏰ Quando: [{orario}] | ⚙️ Azione: {dettagli}")
        
        return "Ecco i task attualmente programmati e attivi nel sistema:\n" + "\n".join(lista_task)
    except Exception as e:
        return f"Errore durante la lettura dei task: {e}"
    

@tool
def elimina_task_programmato(parola_chiave: str) -> str:
    """
    Usa questo tool per eliminare un task programmato o un promemoria.
    Passa una parola chiave univoca contenuta nel task per trovarlo ed eliminarlo.
    """
    print(f"🗑️ [TOOL: Scheduler] Richiesta eliminazione task con keyword: '{parola_chiave}'")
    
    try:
        jobs = scheduler.get_jobs()
        if not jobs:
            return "Non ci sono task programmati al momento nel database."

        task_eliminati = 0
        dettagli_eliminati = []

        for job in jobs:
            # APScheduler salva il prompt del task negli argomenti (job.args[0])
            testo_task = ""
            if job.args and len(job.args) > 0:
                testo_task = str(job.args[0])

            # Se la parola chiave è nel testo del task, lo eliminiamo
            if parola_chiave.lower() in testo_task.lower():
                scheduler.remove_job(job.id)
                task_eliminati += 1
                dettagli_eliminati.append(testo_task)

        if task_eliminati > 0:
            return f"Eliminati {task_eliminati} task con successo:\n" + "\n".join([f"- {t}" for t in dettagli_eliminati])

        return f"Nessun task trovato corrispondente alla parola chiave: '{parola_chiave}'."
        
    except Exception as e:
        return f"Errore durante l'eliminazione del task: {e}"

@tool
async def modifica_task_programmato(
    parola_chiave: str, 
    nuova_istruzione: str = "", 
    nuovi_minuti_attesa: int = 0, 
    cron_minute: str = "", 
    cron_hour: str = "", 
    cron_day: str = "", 
    cron_month: str = "", 
    cron_day_of_week: str = "",
    cron_year: str = ""
) -> str:
    """
    Modifica un task esistente cercando la sua parola chiave. 
    Permette di aggiornare l'istruzione (cosa fare) e/o l'orario (quando farlo).
    - Se non specifichi nuova_istruzione, verrà mantenuta quella vecchia.
      ⚠️ IMPORTANTE: Se l'istruzione originale contiene frasi come "Ogni martedì alle 8", DEVI obbligatoriamente compilare `nuova_istruzione` con il testo aggiornato (es. "Ogni lunedì alle 7"), altrimenti il testo vecchio rimarrà nel database e creerà confusione in futuro!
    - Se specifichi nuovi_minuti_attesa, cambierà in un task singolo tra N minuti.
    - Se specifichi QUALSIASI dei campi cron_*, modificherà l'orario usando la sintassi cron di APScheduler.
      Attenzione: compila tutti i campi cron necessari per la ricorrenza desiderata (es. cron_hour="9" e cron_minute="0").
    - Se non specifichi NESSUN orario (niente minuti_attesa e niente campi cron), manterrà esattamente il trigger originale.
    """
    print(f"✏️ [TOOL: Scheduler] Richiesta modifica task per keyword: '{parola_chiave}'")
    try:
        from core.scheduler import scheduler, _esegui_agente_in_background
        
        chat_id_path = os.path.join("sandbox", "tg_chat_id.txt")
        chat_id = ""
        if os.path.exists(chat_id_path):
            with open(chat_id_path, "r") as f:
                chat_id = f.read().strip()
                
        jobs = scheduler.get_jobs()
        target_job = None
        for job in jobs:
            testo_task = str(job.args[0]) if job.args and len(job.args) > 0 else ""
            if parola_chiave.lower() in testo_task.lower():
                target_job = job
                break
                
        if not target_job:
            return f"Nessun task trovato corrispondente alla parola chiave: '{parola_chiave}'."
            
        testo_originale = str(target_job.args[0]) if target_job.args and len(target_job.args) > 0 else ""
        istruzione_finale = nuova_istruzione if nuova_istruzione.strip() else testo_originale
        
        # Salviamo il vecchio trigger per backup in caso di errore di parsing
        vecchio_trigger = target_job.trigger
        scheduler.remove_job(target_job.id)
        
        has_cron = any([cron_minute, cron_hour, cron_day, cron_month, cron_day_of_week, cron_year])
        
        if has_cron:
            cron_kwargs = {}
            if cron_minute: cron_kwargs['minute'] = cron_minute
            if cron_hour: cron_kwargs['hour'] = cron_hour
            if cron_day: cron_kwargs['day'] = cron_day
            if cron_month: cron_kwargs['month'] = cron_month
            if cron_day_of_week: cron_kwargs['day_of_week'] = cron_day_of_week
            if cron_year: cron_kwargs['year'] = cron_year
            
            try:
                scheduler.add_job(_esegui_agente_in_background, 'cron', args=[istruzione_finale, chat_id], **cron_kwargs)
            except Exception as cron_err:
                scheduler.add_job(_esegui_agente_in_background, trigger=vecchio_trigger, args=[testo_originale, chat_id])
                return f"Errore di sintassi Cron: {cron_err}. Il task non è stato modificato ed è stato ripristinato."
                
            return f"✅ Task modificato con parametri cron: {cron_kwargs}. Nuova istruzione: '{istruzione_finale}'."
            
        elif nuovi_minuti_attesa > 0:
            orario_locale_attuale = datetime.now(timezone.utc).astimezone()
            dt_obj = orario_locale_attuale + timedelta(minutes=nuovi_minuti_attesa)
            scheduler.add_job(_esegui_agente_in_background, 'date', run_date=dt_obj, args=[istruzione_finale, chat_id])
            return f"✅ Task modificato: armato per le {dt_obj.strftime('%H:%M:%S')}. Nuova istruzione: '{istruzione_finale}'."
            
        else:
            scheduler.add_job(_esegui_agente_in_background, trigger=vecchio_trigger, args=[istruzione_finale, chat_id])
            return f"✅ Task modificato mantenendo l'orario originale. Nuova istruzione: '{istruzione_finale}'."
            
    except Exception as e:
        return f"Errore durante la modifica del task: {e}"
    

@tool
def controlla_notifiche_discord() -> str:
    """
    Controlla le menzioni recenti e i messaggi non letti su Discord dell'utente.
    Richiede DISCORD_TOKEN nel file .env.
    """
    import requests
    import os
    
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        return "Errore: DISCORD_TOKEN non configurato nel file .env."
        
    headers = {"Authorization": token, "Content-Type": "application/json"}
    
    try:
        # Endpoint per recuperare le menzioni recenti dell'utente
        res = requests.get("https://discord.com/api/v9/users/@me/mentions?limit=5", headers=headers, timeout=10)
        
        if res.status_code == 200:
            mentions = res.json()
            if not mentions:
                return "Nessuna nuova menzione o notifica urgente su Discord."
            
            report = "🔔 NOTIFICHE DISCORD:\n"
            for m in mentions:
                autore = m.get('author', {}).get('username', 'Sconosciuto')
                canale = m.get('channel_id', 'Privato')
                contenuto = m.get('content', '')[:60]
                report += f"- Da {autore} (Canale: {canale}): {contenuto}...\n"
            return report
        elif res.status_code == 401:
            return "Errore Discord: Token non valido o scaduto."
        else:
            return f"Errore Discord: Status {res.status_code}"
            
    except Exception as e:
        return f"Errore durante la connessione a Discord: {e}"
    
@tool
def invia_documento_telegram(percorso_file: str, didascalia: str = "") -> str:
    """
    Invia un file esistente (PDF, MP4, JPG, ecc.) all'utente su Telegram.
    Esempio: percorso_file='sandbox/riassunto.pdf'
    """
    import os
    import httpx
    
    token = os.getenv("TELEGRAM_TOKEN")
    # Recuperiamo il chat_id dal file che salva il sistema
    chat_id_path = os.path.join("sandbox", "tg_chat_id.txt")
    
    if not os.path.exists(chat_id_path) or not token:
        return "❌ Errore: Configurazione Telegram mancante."
    
    if not os.path.exists(percorso_file):
        return f"❌ Errore: Il file {percorso_file} non esiste sul disco."

    with open(chat_id_path, "r") as f:
        chat_id = f.read().strip()

    url = f"https://api.telegram.org/bot{token}/sendDocument"
    
    try:
        with open(percorso_file, "rb") as f:
            files = {"document": f}
            data = {"chat_id": chat_id, "caption": didascalia}
            res = httpx.post(url, data=data, files=files, timeout=30.0)
            
        if res.status_code == 200:
            return f"✅ File {os.path.basename(percorso_file)} inviato con successo su Telegram!"
        else:
            return f"❌ Errore Telegram: {res.text}"
    except Exception as e:
        return f"❌ Errore durante l'invio del file: {e}"
    

tools = [
    ottieni_data_ora_sistema,
    ricerca_web_affidabile,
    analyze_local_image,
    execute_python_code,
    save_memory,
    search_memory,
    programma_task_autonomo,
    apri_in_vscode,
    apri_sito_web_universale,
    invia_email_universale,
    genera_immagine_locale,
    leggi_ultime_email,
    invia_email_google,
    leggi_prossimi_eventi_calendario,
    esplora_file_sistema,
    leggi_file_sistema,
    scrivi_o_copia_file,
    gestisci_file_avanzato,
    leggi_whatsapp,
    leggi_telegram_personale,
    scatta_e_analizza_schermo,
    esegui_azione_mouse_tastiera, 
    navigatore_web_integrato,
    leggi_tutte_le_chat,
    leggi_pagina_web,
    crea_documento_pdf,
    leggi_documento, 
    leggi_task_programmati,
    controlla_notifiche_discord,
    invia_documento_telegram
]
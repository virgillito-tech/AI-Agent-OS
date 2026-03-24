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

# -------------------------------------------------------------
# FIX INFORMATICO DEFINITIVO (Pydantic V2)
# La classe personalizzata DEVE risiedere nel contesto globale.
# In questo modo Pydantic la valida correttamente e non distrugge
# i metodi asincroni nativi di LangChain (come .ainvoke).
# -------------------------------------------------------------
class SafeBrowserLLM(ChatOpenAI):
    """LLM corazzato per aggirare i limiti di browser_use."""
    provider: str = Field(default="openai")
    tiktoken_model_name: str = Field(default="gpt-4o")

    def __setattr__(self, name, value):
        # FIX INFORMATICO: Quando browser_use tenta di "hackerare" il metodo ainvoke 
        # per tracciare i token, bypassiamo Pydantic e lo salviamo a basso livello.
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
def ricerca_web_affidabile(query: str) -> str:
    """
    Esegue una ricerca su Internet.
    OBBLIGATORIO per: notizie recenti, risultati sportivi, previsioni meteo, eventi attuali.
    Usa query brevi e concise (es. 'risultati champions league 11 marzo 2026').
    """
    print(f"\n🌐 [TOOL: Ricerca Web] Avvio ricerca per: '{query}'")
    try:
        url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}"
        headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
        
        res = requests.get(url, headers=headers, timeout=(3.0, 7.0))
        res.raise_for_status()
        
        soup = BeautifulSoup(res.text, "html.parser")
        
        risultati_formattati = []
        # Cerchiamo i blocchi dei risultati
        for div in soup.find_all("div", class_="result__body", limit=6):
            titolo_tag = div.find("a", class_="result__a")
            snippet_tag = div.find("a", class_="result__snippet")
            
            if titolo_tag and snippet_tag:
                titolo = titolo_tag.text.strip()
                link = titolo_tag.get('href', 'Link non disponibile')
                # DuckDuckGo usa dei redirect, li puliamo se possibile
                if "uddg=" in link:
                    link = urllib.parse.unquote(link.split("uddg=")[1].split("&")[0])
                    
                snippet = snippet_tag.text.strip()
                risultati_formattati.append(f"Titolo: {titolo}\nLink: {link}\nEstratto: {snippet}")
        
        if not risultati_formattati:
            return "Nessun risultato testuale trovato."
            
        final_text = "\n---\n".join(risultati_formattati)
        print(f"🌐 [TOOL: Ricerca Web] ✅ Trovati {len(risultati_formattati)} risultati.")
        return final_text
    except Exception as e:
        print(f"🌐 [TOOL: Ricerca Web] ❌ ERRORE DI RETE: {str(e)}")
        return f"Errore di rete durante la ricerca web: {str(e)}"
    

def _get_vision_llm():
    from langchain_ollama import ChatOllama
    return ChatOllama(model=config.VISION_MODEL_NAME, temperature=0)

def process_image(prompt_text: str, base64_image: str) -> str:
    print(f"👁️ [TOOL: Visione] Analisi immagine in corso...")
    vision_llm = _get_vision_llm()
    system_instruction = "Sei un analista visivo. Traduci e descrivi in italiano."
    full_prompt = f"{system_instruction}\n\nRichiesta: {prompt_text}"
    message = HumanMessage(content=[
        {"type": "text", "text": full_prompt},
        {"type": "image_url", "image_url": f"data:image/jpeg;base64,{base64_image}"},
    ])
    res = vision_llm.invoke([message]).content
    print(f"👁️ [TOOL: Visione] Analisi completata.")
    return res

@tool
def analyze_local_image(image_path: str, user_prompt: str = "") -> str:
    """Analizza una tavola manga o un'immagine locale."""
    try:
        with open(image_path, "rb") as image_file:
            image_base64 = base64.b64encode(image_file.read()).decode("utf-8")
        return process_image(user_prompt, image_base64)
    except Exception as e: return f"Errore analisi immagine: {e}"

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

@tool
def leggi_whatsapp(nome_contatto: str) -> str:
    """
    Legge gli ultimi messaggi da una chat specifica di WhatsApp personale dell'utente.
    """
    print(f"🟢 [TOOL: WhatsApp] Tento di leggere la chat con: {nome_contatto}")
    try:
        from playwright.sync_api import sync_playwright
        import time
        
        user_data_dir = os.path.abspath(os.path.join("sandbox", "wa_session"))
        
        with sync_playwright() as p:
            browser = p.chromium.launch_persistent_context(
                user_data_dir, 
                headless=False 
            )
            page = browser.new_page()
            page.goto("https://web.whatsapp.com/")
            
            print("⏳ Attendo il caricamento di WhatsApp Web (o lo scan del QR)...")
            page.wait_for_selector('div[contenteditable="true"]', timeout=60000)
            
            search_box = page.locator('div[contenteditable="true"][data-tab="3"]')
            search_box.fill(nome_contatto)
            time.sleep(2)
            page.keyboard.press("Enter")
            time.sleep(3) 
            
            messages = page.locator('div.message-in, div.message-out').all_inner_texts()
            
            browser.close()
            
            if not messages:
                return f"Nessun messaggio trovato nella chat con {nome_contatto}."
            
            ultimi_msg = "\n".join(messages[-5:])
            return f"Ultimi messaggi con {nome_contatto}:\n{ultimi_msg}"
            
    except Exception as e:
        return f"Errore durante l'accesso a WhatsApp: {str(e)}. (L'utente potrebbe dover effettuare il login)."

@tool
def leggi_telegram_personale(nome_contatto_o_username: str) -> str:
    """
    Legge gli ultimi messaggi scambiati sull'account personale Telegram dell'utente con un contatto.
    """
    print(f"🔵 [TOOL: Telegram Personal] Lettura chat con: {nome_contatto_o_username}")
    import asyncio
    from telethon.sync import TelegramClient
    
    session_path = os.path.join("sandbox", "tg_personal_session")
    
    def _run_telethon():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        client = TelegramClient(session_path, config.TG_API_ID, config.TG_API_HASH)
        
        with client:
            messages = client.get_messages(nome_contatto_o_username, limit=5)
            
            if not messages:
                return "Nessun messaggio trovato."
                
            res = []
            for m in reversed(messages):
                mittente = "Io" if m.out else nome_contatto_o_username
                testo = m.message or "[Media/Non testuale]"
                res.append(f"{mittente}: {testo}")
                
            return "\n".join(res)

    try:
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as pool:
            future = pool.submit(_run_telethon)
            return future.result(timeout=60)
    except Exception as e:
        return f"Errore Telethon: {str(e)}"
    
@tool
def scatta_e_analizza_schermo(domanda: str) -> str:
    """
    Scatta uno screenshot dello schermo attuale e lo fa analizzare al modello di Visione.
    Usa questo tool per capire cosa c'è a schermo, trovare le coordinate (X, Y) di bottoni, icone o leggere testo visibile.
    """
    print(f"📸 [TOOL: Visione] Scatto screenshot in corso...")
    try:
        with mss.mss() as sct:
            monitor = sct.monitors[1]
            screenshot_path = os.path.join("sandbox", "current_screen.png")
            sct.shot(output=screenshot_path)

        print(f"👁️ [TOOL: Visione] Analisi dell'immagine per: '{domanda}'")
        
        with open(screenshot_path, "rb") as image_file:
            image_base64 = base64.b64encode(image_file.read()).decode("utf-8")
        
        vision_llm = _get_vision_llm()
        system_instruction = "Sei un'AI specializzata in UI/UX e automazione desktop. Analizza lo screenshot fornito e rispondi alla domanda dell'utente. Se ti vengono chieste coordinate per cliccare, stima le coordinate X e Y approssimative in pixel (il monitor parte da X=0, Y=0 in alto a sinistra)."
        
        message = HumanMessage(content=[
            {"type": "text", "text": f"{system_instruction}\n\nDomanda: {domanda}"},
            {"type": "image_url", "image_url": f"data:image/jpeg;base64,{image_base64}"},
        ])
        
        res = vision_llm.invoke([message]).content
        return res
    except Exception as e:
        return f"Errore durante lo screenshot o l'analisi visiva: {e}"

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
async def programma_task_autonomo(istruzione: str, minuti_attesa: int = 0, ora_ricorrente: str = "") -> str:
    """
    Programma un task in cui TU STESSO (Agente) dovrai fare ricerche, analizzare dati o eseguire azioni nel futuro.
    - Per task singolo: usa 'minuti_attesa' (es. 60 per tra un'ora).
    - Per task GIORNALIERO RICORRENTE: usa 'ora_ricorrente' (es. "09:00").
    L'istruzione deve descrivere ESATTAMENTE cosa dovrai fare (es. "Cerca le notizie AI e fai un riassunto").
    """
    print(f"📅 [TOOL: Scheduler] Richiesta autonomia: minuti={minuti_attesa}, ricorrente={ora_ricorrente}")
    try:
        from core.scheduler import scheduler, _esegui_agente_in_background
        
        chat_id_path = os.path.join("sandbox", "tg_chat_id.txt")
        if not os.path.exists(chat_id_path):
            return "Errore: Manca il Chat ID di Telegram nella sandbox."
            
        with open(chat_id_path, "r") as f:
            chat_id = f.read().strip()

        if ora_ricorrente:
            ore, minuti_orario = map(int, ora_ricorrente.split(":"))
            scheduler.add_job(
                _esegui_agente_in_background, 'cron', hour=ore, minute=minuti_orario, args=[istruzione, chat_id]
            )
            return f"✅ Task giornaliero impostato. Ogni giorno alle {ora_ricorrente} mi sveglierò ed eseguirò: '{istruzione}'."
            
        elif minuti_attesa > 0:
            orario_locale_attuale = datetime.now(timezone.utc).astimezone()
            dt_obj = orario_locale_attuale + timedelta(minutes=minuti_attesa)
            scheduler.add_job(
                _esegui_agente_in_background, 'date', run_date=dt_obj, args=[istruzione, chat_id]
            )
            return f"✅ Task autonomo armato per le {dt_obj.strftime('%H:%M:%S')}."
            
        else: return "Errore: specificare minuti_attesa o ora_ricorrente."
            
    except Exception as e: return f"Errore critico nella pianificazione: {e}"

@tool
async def navigatore_web_integrato(istruzioni: str) -> str:
    """STRUMENTO UFFICIALE: Navigatore Web Nativo (Browser Use)."""
    print(f"🌐 [BROWSER AI] Avvio navigazione per: {istruzioni}")
    try:
        from browser_use import Agent
        import config

        engine = getattr(config, "ACTIVE_ENGINE", "ollama")

        if engine == "mlx":
            url = getattr(config, "MLX_BASE_URL", "http://localhost:8080").rstrip("/") + "/v1"
            modello = getattr(config, "MLX_TEXT_MODEL_NAME", "mlx-community/Qwen3.5-9B-MLX-4bit")
        else:
            url = getattr(config, "BASE_URL_TEXT", "http://localhost:11434").rstrip("/") + "/v1"
            modello = getattr(config, "TEXT_MODEL_NAME", "qwen3.5:9b")

        llm_guida = SafeBrowserLLM(
            base_url=url,
            api_key="ollama", 
            model=modello,
            temperature=0.0,
        )

        browser_agent = Agent(task=istruzioni, llm=llm_guida)
        history = await browser_agent.run()

        risultato = history.final_result()
        if not risultato:
            return "Navigazione completata, ma nessun dato testuale restituito dalla pagina."

        print(f"🌐 [BROWSER AI] ✅ Navigazione completata.")
        return f"Risultato della navigazione web:\n{risultato}"

    except Exception as e:
        import traceback
        errore_stack = traceback.format_exc()
        print(f"\n🌐 [BROWSER AI] ❌ ERRORE CRITICO INTERNO:\n{errore_stack}\n")
        return f"Errore critico durante la navigazione: {str(e)}"
    

@tool
def leggi_tutte_le_chat() -> str:
    """
    Legge in un colpo solo tutti i messaggi NON LETTI da Telegram e WhatsApp.
    Usa questo tool per avere un riepilogo rapido delle comunicazioni in sospeso dell'utente.
    """
    print("📱 [TOOL: Comunicazioni] Avvio lettura unificata chat...")
    return chat_reader.leggi_tutte_le_chat()

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
        
        max_chars = 15000 
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
    leggi_documento
]
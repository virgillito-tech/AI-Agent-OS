import sys
import re

with open("tools/agent_tools.py", "r", encoding="utf-8") as f:
    content = f.read()

# Define start and end markers
start_marker = '@tool\ndef gestisci_calendario_mac'
end_marker = 'invia_documento_telegram\n]'

start_idx = content.find(start_marker)
end_idx = content.find(end_marker) + len(end_marker)

if start_idx == -1 or end_idx < start_idx:
    print("Could not find markers.")
    sys.exit(1)

new_code = """@tool
def gestisci_calendario_universale(azione: str, titolo: str = "", data_inizio: str = "", data_fine: str = "") -> str:
    \"\"\"
    Legge o aggiunge eventi al Calendario (universale).
    - azione: "leggi" (solo Mac) o "aggiungi" (Windows/Mac/Linux tramite file .ics).
    - titolo: Il nome dell'evento (solo per "aggiungi").
    - data_inizio: Data/ora inizio in formato "YYYY-MM-DD HH:MM:SS" (solo per "aggiungi").
    - data_fine: Data/ora fine in formato "YYYY-MM-DD HH:MM:SS" (solo per "aggiungi").
    \"\"\"
    import subprocess
    import datetime
    import uuid
    import os
    import tempfile
    import webbrowser
    import platform
    
    if azione == "leggi":
        if platform.system() == "Darwin":
            script = '''
            tell application "Calendar"
                set today to current date
                set time of today to 0
                set tomorrow to today + (2 * days)
                set eventList to ""
                repeat with c in calendars
                    set calEvents to (every event of c whose start date is greater than today and start date is less than tomorrow)
                    repeat with e in calEvents
                        set eventList to eventList & "- " & (summary of e) & " (\\n"
                    end repeat
                end repeat
                return eventList
            end tell
            '''
            res = subprocess.run(['osascript', '-e', script], capture_output=True, text=True)
            if not res.stdout.strip():
                return "Nessun evento in programma per oggi o domani."
            return f"📅 Eventi in calendario:\\n{res.stdout.strip()}"
        else:
            return "Errore: La lettura del calendario locale è supportata solo su Mac. Usa i tool Google Calendar per Windows/Linux."
            
    elif azione == "aggiungi":
        if not titolo or not data_inizio or not data_fine:
            return "Errore: per aggiungere un evento devi specificare titolo, data_inizio e data_fine."
        
        try:
            dt_start = datetime.datetime.strptime(data_inizio, "%Y-%m-%d %H:%M:%S")
            dt_end = datetime.datetime.strptime(data_fine, "%Y-%m-%d %H:%M:%S")
            ics_content = f\"\"\"BEGIN:VCALENDAR\\nVERSION:2.0\\nBEGIN:VEVENT\\nSUMMARY:{titolo}\\nDTSTART:{dt_start.strftime('%Y%m%dT%H%M%S')}\\nDTEND:{dt_end.strftime('%Y%m%dT%H%M%S')}\\nEND:VEVENT\\nEND:VCALENDAR\"\"\"
            path = os.path.join(tempfile.gettempdir(), f"evento_{uuid.uuid4().hex}.ics")
            with open(path, "w") as f: f.write(ics_content)
            webbrowser.open("file://" + path)
            return "✅ Evento preparato. Si aprirà l'app Calendario predefinita per confermare l'aggiunta."
        except Exception as e:
            return f"Errore: {e}"

@tool
def gestore_multimediale(comando: str, piattaforma: str = "spotify") -> str:
    \"\"\"
    Controlla la riproduzione musicale del sistema in modo universale.
    - comando: "play", "pause", "next track", "previous track".
    \"\"\"
    import pyautogui
    try:
        if comando in ["play", "pause"]:
            pyautogui.press("playpause")
        elif "next" in comando:
            pyautogui.press("nexttrack")
        elif "previous" in comando or "prev" in comando:
            pyautogui.press("prevtrack")
        else:
            return "Comando non supportato."
        return f"✅ Comando multimediale '{comando}' inviato al sistema."
    except Exception as e:
        return f"Errore nell'invio del comando multimediale. Assicurati che pyautogui sia installato (pip install pyautogui): {e}"

@tool
def parla_con_utente(testo: str) -> str:
    \"\"\"
    Fa pronunciare ad alta voce al computer una frase o un breve messaggio.
    Universale: supporta Mac, Windows e Linux.
    \"\"\"
    import subprocess
    import platform
    
    sys_name = platform.system()
    try:
        if sys_name == "Darwin":
            subprocess.run(["say", testo])
        elif sys_name == "Windows":
            cmd = f"Add-Type -AssemblyName System.Speech; (New-Object System.Speech.Synthesis.SpeechSynthesizer).Speak('{testo.replace(chr(39), chr(39)+chr(39))}')"
            subprocess.run(["powershell", "-Command", cmd])
        elif sys_name == "Linux":
            subprocess.run(["espeak", testo])
        return f"🗣️ Ho pronunciato ad alta voce: '{testo}'"
    except Exception as e:
        return f"Errore durante la sintesi vocale: {e}"

@tool
def trascrivi_e_riassumi_audio(file_path: str) -> str:
    \"\"\"
    Usa Whisper locale per trascrivere un file audio e ne restituisce il testo.
    \"\"\"
    import os
    if not os.path.exists(file_path):
        return f"Errore: file audio {file_path} non trovato."
    
    try:
        from faster_whisper import WhisperModel
        model = WhisperModel("base", device="cpu", compute_type="int8")
        segments, info = model.transcribe(file_path)
        testo = " ".join([segment.text for segment in segments])
        return f"📝 Trascrizione Audio ({info.language}):\\n{testo}"
    except Exception as e:
        return f"Errore durante la trascrizione: {e}"

@tool
def gestisci_note_obsidian(azione: str, nome_nota: str, contenuto: str = "") -> str:
    \"\"\"
    Legge, crea o aggiunge testo a una nota Markdown nel Vault di Obsidian.
    - azione: "leggi", "scrivi" (sovrascrive), "aggiungi" (append).
    - nome_nota: Il nome della nota (es. "Idee.md").
    - contenuto: Il testo da inserire.
    \"\"\"
    import os
    vault_path = os.getenv("OBSIDIAN_VAULT_PATH", os.path.expanduser("~/Documents/Obsidian Vault"))
    if not os.path.exists(vault_path):
        os.makedirs(vault_path, exist_ok=True)
            
    if not nome_nota.endswith(".md"): nome_nota += ".md"
    full_path = os.path.join(vault_path, nome_nota)
    
    try:
        if azione == "leggi":
            if not os.path.exists(full_path): return "Nota non trovata."
            with open(full_path, "r", encoding="utf-8") as f: return f.read()
        elif azione == "scrivi":
            with open(full_path, "w", encoding="utf-8") as f: f.write(contenuto)
            return f"✅ Nota '{nome_nota}' creata/sovrascritta."
        elif azione == "aggiungi":
            with open(full_path, "a", encoding="utf-8") as f: f.write("\\n" + contenuto)
            return f"✅ Testo aggiunto alla nota '{nome_nota}'."
        else: return "Azione non valida."
    except Exception as e: return f"Errore: {e}"

@tool
def esegui_comando_terminale_sandbox(comando: str) -> str:
    \"\"\"
    Esegue un comando shell (cmd/powershell su Windows, bash su Mac/Linux). Timeout 30s.
    \"\"\"
    import subprocess
    try:
        res = subprocess.run(comando, shell=True, capture_output=True, text=True, timeout=30)
        out = res.stdout if res.stdout else res.stderr
        return f"💻 Risultato ({res.returncode}):\\n{out[:4000]}"
    except subprocess.TimeoutExpired: return "⏳ Errore: Timeout superato."
    except Exception as e: return f"❌ Errore esecuzione: {e}"

@tool
def gestisci_applicazioni_universale(azione: str, nome_app: str) -> str:
    \"\"\"
    Apre o chiude forzatamente un'applicazione (universale per Mac/Windows/Linux).
    - azione: "apri" o "chiudi".
    \"\"\"
    import subprocess
    import platform
    import psutil
    import os
    import webbrowser
    
    sys_name = platform.system()
    try:
        if azione == "apri":
            if sys_name == "Darwin":
                subprocess.run(["open", "-a", nome_app])
            elif sys_name == "Windows":
                subprocess.run(f"start {nome_app}", shell=True)
            else:
                subprocess.Popen(nome_app, shell=True)
        elif azione == "chiudi":
            killed = 0
            for proc in psutil.process_iter(['pid', 'name']):
                if proc.info['name'] and nome_app.lower() in proc.info['name'].lower():
                    proc.kill()
                    killed += 1
            if killed == 0:
                return f"Nessun processo trovato per l'app '{nome_app}'."
        else: return "Azione non supportata."
        return f"✅ Applicazione '{nome_app}' gestita con successo ({azione})."
    except Exception as e: return f"Errore: {e}"

@tool
def pubblica_su_social(piattaforma: str, testo_post: str) -> str:
    \"\"\"
    Prepara una bozza di post per i social media (twitter, linkedin) e apre il browser (universale).
    \"\"\"
    import urllib.parse
    import webbrowser
    import tkinter as tk
    
    if piattaforma.lower() in ["twitter", "x"]:
        url = f"https://twitter.com/intent/tweet?text={urllib.parse.quote(testo_post)}"
        webbrowser.open(url)
        return f"✅ Browser aperto su Twitter."
    elif piattaforma.lower() == "linkedin":
        try:
            r = tk.Tk()
            r.withdraw()
            r.clipboard_clear()
            r.clipboard_append(testo_post)
            r.update()
            r.destroy()
            msg = "✅ Testo copiato negli appunti e browser aperto su LinkedIn."
        except:
            msg = "✅ Browser aperto su LinkedIn. (Copia il testo manualmente: il modulo tkinter non è disponibile)."
        webbrowser.open("https://www.linkedin.com/feed/")
        return msg
    return "Piattaforma non supportata."

# END NEW TOOLS


tools = [
    gestisci_calendario_universale,
    gestore_multimediale,
    parla_con_utente,
    trascrivi_e_riassumi_audio,
    gestisci_note_obsidian,
    esegui_comando_terminale_sandbox,
    gestisci_applicazioni_universale,
    pubblica_su_social,
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
]"""

new_content = content[:start_idx] + new_code + content[end_idx:]

with open("tools/agent_tools.py", "w", encoding="utf-8") as f:
    f.write(new_content)

print("Replacement successful.")

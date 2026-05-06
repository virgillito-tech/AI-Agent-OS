import sys

with open("tools/agent_tools.py", "r", encoding="utf-8") as f:
    content = f.read()

new_tools_code = """
@tool
def gestisci_calendario_mac(azione: str, titolo: str = "", data_inizio: str = "", data_fine: str = "") -> str:
    \"\"\"
    Legge o aggiunge eventi al Calendario di default del Mac.
    - azione: "leggi" (per ottenere gli eventi di oggi e domani) o "aggiungi".
    - titolo: Il nome dell'evento (solo per "aggiungi").
    - data_inizio: Data/ora inizio in formato "YYYY-MM-DD HH:MM:SS" (solo per "aggiungi").
    - data_fine: Data/ora fine in formato "YYYY-MM-DD HH:MM:SS" (solo per "aggiungi").
    \"\"\"
    import subprocess
    import datetime
    import uuid
    import os
    
    if azione == "leggi":
        script = '''
        tell application "Calendar"
            set today to current date
            set time of today to 0
            set tomorrow to today + (2 * days)
            set eventList to ""
            repeat with c in calendars
                set calEvents to (every event of c whose start date is greater than today and start date is less than tomorrow)
                repeat with e in calEvents
                    set eventList to eventList & "- " & (summary of e) & " (" & (start date of e) & ")\\n"
                end repeat
            end repeat
            return eventList
        end tell
        '''
        res = subprocess.run(['osascript', '-e', script], capture_output=True, text=True)
        if not res.stdout.strip():
            return "Nessun evento in programma per oggi o domani."
        return f"📅 Eventi in calendario:\\n{res.stdout.strip()}"
        
    elif azione == "aggiungi":
        if not titolo or not data_inizio or not data_fine:
            return "Errore: per aggiungere un evento devi specificare titolo, data_inizio e data_fine."
        
        try:
            dt_start = datetime.datetime.strptime(data_inizio, "%Y-%m-%d %H:%M:%S")
            dt_end = datetime.datetime.strptime(data_fine, "%Y-%m-%d %H:%M:%S")
            ics_content = f\"\"\"BEGIN:VCALENDAR\\nVERSION:2.0\\nBEGIN:VEVENT\\nSUMMARY:{titolo}\\nDTSTART:{dt_start.strftime('%Y%m%dT%H%M%S')}\\nDTEND:{dt_end.strftime('%Y%m%dT%H%M%S')}\\nEND:VEVENT\\nEND:VCALENDAR\"\"\"
            path = f"/tmp/evento_{uuid.uuid4().hex}.ics"
            with open(path, "w") as f: f.write(ics_content)
            subprocess.run(["open", path])
            return "✅ Evento preparato. Si aprirà l'app Calendario per confermare l'aggiunta."
        except Exception as e:
            return f"Errore: {e}"

@tool
def gestore_multimediale(comando: str, piattaforma: str = "spotify") -> str:
    \"\"\"
    Controlla la riproduzione musicale.
    - comando: "play", "pause", "next track", "previous track".
    - piattaforma: "spotify" o "music" (Apple Music).
    \"\"\"
    import subprocess
    app = "Spotify" if piattaforma.lower() == "spotify" else "Music"
    script = f'tell application "{app}" to {comando}'
    res = subprocess.run(['osascript', '-e', script], capture_output=True, text=True)
    if res.returncode != 0:
        return f"Errore: Assicurati che l'app {app} sia aperta. Dettagli: {res.stderr.strip()}"
    return f"✅ Comando '{comando}' eseguito su {app}."

@tool
def parla_con_utente(testo: str) -> str:
    \"\"\"
    Fa pronunciare ad alta voce al computer una frase o un breve messaggio.
    Utile per dare risposte vocali all'utente o avvisi importanti.
    \"\"\"
    import subprocess
    subprocess.run(["say", testo])
    return f"🗣️ Ho pronunciato ad alta voce: '{testo}'"

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
    Esegue un comando shell sul Mac (es. ls, ping, echo). Timeout 30s.
    \"\"\"
    import subprocess
    try:
        res = subprocess.run(comando, shell=True, capture_output=True, text=True, timeout=30)
        out = res.stdout if res.stdout else res.stderr
        return f"💻 Risultato ({res.returncode}):\\n{out[:4000]}"
    except subprocess.TimeoutExpired: return "⏳ Errore: Timeout superato."
    except Exception as e: return f"❌ Errore esecuzione: {e}"

@tool
def gestisci_applicazioni_mac(azione: str, nome_app: str) -> str:
    \"\"\"
    Apre o chiude forzatamente un'applicazione sul Mac.
    - azione: "apri" o "chiudi".
    \"\"\"
    import subprocess
    try:
        if azione == "apri":
            res = subprocess.run(["open", "-a", nome_app], capture_output=True, text=True)
        elif azione == "chiudi":
            res = subprocess.run(["killall", nome_app], capture_output=True, text=True)
        else: return "Azione non supportata."
        if res.returncode != 0: return f"Errore: {res.stderr}"
        return f"✅ App '{nome_app}' gestita con successo."
    except Exception as e: return f"Errore: {e}"

@tool
def pubblica_su_social(piattaforma: str, testo_post: str) -> str:
    \"\"\"
    Prepara una bozza di post per i social media (twitter, linkedin) e apre il browser.
    \"\"\"
    import urllib.parse
    import subprocess
    
    if piattaforma.lower() in ["twitter", "x"]:
        url = f"https://twitter.com/intent/tweet?text={urllib.parse.quote(testo_post)}"
        subprocess.run(["open", url])
        return f"✅ Browser aperto su Twitter."
    elif piattaforma.lower() == "linkedin":
        # Per linkedin bisogna incollare il testo a mano
        subprocess.run("pbcopy", universal_newlines=True, input=testo_post)
        subprocess.run(["open", "https://www.linkedin.com/feed/"])
        return "✅ Testo copiato negli appunti e browser aperto su LinkedIn."
    return "Piattaforma non supportata."

# END NEW TOOLS
"""

# Replace tools list in agent_tools.py
parts = content.split("tools = [")
new_tools_list = """tools = [
    gestisci_calendario_mac,
    gestore_multimediale,
    parla_con_utente,
    trascrivi_e_riassumi_audio,
    gestisci_note_obsidian,
    esegui_comando_terminale_sandbox,
    gestisci_applicazioni_mac,
    pubblica_su_social,"""

new_content = parts[0] + new_tools_code + "\n\n" + new_tools_list + parts[1]

with open("tools/agent_tools.py", "w", encoding="utf-8") as f:
    f.write(new_content)

print("Tools appended successfully.")

import sys

with open("tools/agent_tools.py", "r", encoding="utf-8") as f:
    content = f.read()

# 1. Replace gestisci_calendario_mac
old_cal = """@tool
def gestisci_calendario_mac(azione: str, titolo: str = "", data_inizio: str = "", data_fine: str = "") -> str:"""

new_cal = """@tool
def gestisci_calendario_universale(azione: str, titolo: str = "", data_inizio: str = "", data_fine: str = "") -> str:
    \"\"\"
    Legge o aggiunge eventi al Calendario.
    - azione: "leggi" (solo Mac) o "aggiungi" (Windows/Mac/Linux tramite file .ics).
    - titolo: Il nome dell'evento (solo per "aggiungi").
    - data_inizio: Data/ora inizio in formato "YYYY-MM-DD HH:MM:SS" (solo per "aggiungi").
    - data_fine: Data/ora fine in formato "YYYY-MM-DD HH:MM:SS" (solo per "aggiungi").
    \"\"\"
    import subprocess
    import datetime
    import uuid
    import os
    import platform
    import webbrowser
    
    sys_name = platform.system()
    
    if azione == "leggi":
        if sys_name == "Darwin":
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
        else:
            return "Errore: La lettura del calendario locale è supportata solo su Mac. Usa i tool Google Calendar per Windows/Linux."
            
    elif azione == "aggiungi":
        if not titolo or not data_inizio or not data_fine:
            return "Errore: per aggiungere un evento devi specificare titolo, data_inizio e data_fine."
        
        try:
            dt_start = datetime.datetime.strptime(data_inizio, "%Y-%m-%d %H:%M:%S")
            dt_end = datetime.datetime.strptime(data_fine, "%Y-%m-%d %H:%M:%S")
            ics_content = f\"\"\"BEGIN:VCALENDAR\\nVERSION:2.0\\nBEGIN:VEVENT\\nSUMMARY:{titolo}\\nDTSTART:{dt_start.strftime('%Y%m%dT%H%M%S')}\\nDTEND:{dt_end.strftime('%Y%m%dT%H%M%S')}\\nEND:VEVENT\\nEND:VCALENDAR\"\"\"
            path = os.path.join(tempfile.gettempdir() if 'tempfile' in sys.modules else '/tmp', f"evento_{uuid.uuid4().hex}.ics")
            with open(path, "w") as f: f.write(ics_content)
            webbrowser.open("file://" + path)
            return "✅ Evento preparato. Si aprirà l'app Calendario per confermare l'aggiunta."
        except Exception as e:
            return f"Errore: {e}"

@tool"""

content = content.replace(old_cal, new_cal)
# Remove the old docstring and body of gestisci_calendario_mac up to the next @tool
# Wait, this is dangerous with string replacement. I will use a regex.

# tools/os_tools.py
import os
import platform
import subprocess
import psutil
from langchain_core.tools import tool

def get_os() -> str:
    return platform.system().lower()

@tool
def leggi_stato_batteria() -> str:
    """Legge lo stato attuale della batteria del computer (percentuale e se è in carica)."""
    print("🔋 [TOOL: OS] Lettura stato batteria...")
    try:
        battery = psutil.sensors_battery()
        if battery is None:
            return "Nessuna batteria rilevata (probabilmente è un computer fisso)."
        
        percentuale = round(battery.percent)
        in_carica = "Sì" if battery.power_plugged else "No"
        tempo_rimasto = "Sconosciuto"
        if not battery.power_plugged and battery.secsleft > 0:
            ore, resto = divmod(battery.secsleft, 3600)
            minuti, _ = divmod(resto, 60)
            tempo_rimasto = f"{ore}h {minuti}m"
            
        return f"Stato Batteria: {percentuale}%\nIn carica: {in_carica}\nTempo stimato rimanente: {tempo_rimasto}"
    except Exception as e:
        return f"Errore lettura batteria: {e}"

@tool
def sospendi_computer() -> str:
    """Mette istantaneamente il computer in stato di Stop/Ibernazione."""
    print("💤 [TOOL: OS] Comando di Sospensione ricevuto...")
    sistema = get_os()
    try:
        if sistema == "darwin": # Mac
            subprocess.run(["pmset", "sleepnow"], check=True)
            return "Mac messo in stop."
        elif sistema == "windows":
            subprocess.run(["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"], check=True)
            return "PC Windows sospeso."
        elif sistema == "linux":
            subprocess.run(["systemctl", "suspend"], check=True)
            return "Sistema Linux sospeso."
        else:
            return f"Sistema operativo '{sistema}' non supportato per la sospensione."
    except Exception as e:
        return f"Errore durante il comando di sospensione: {e}"

@tool
def apri_applicazione(nome_app: str) -> str:
    """
    Apre un'applicazione specifica sul computer dell'utente (es. 'Spotify', 'Calculator', 'Safari').
    """
    print(f"🚀 [TOOL: OS] Avvio applicazione: {nome_app}...")
    sistema = get_os()
    try:
        if sistema == "darwin":
            subprocess.run(["open", "-a", nome_app], check=True)
            return f"Applicazione '{nome_app}' aperta su Mac."
        elif sistema == "windows":
            # FIX: Il doppio apice vuoto "" previene il bug degli spazi nel nome su Windows
            subprocess.run(["cmd", "/c", "start", "", nome_app], check=True)
            return f"Applicazione '{nome_app}' avviata su Windows."
        elif sistema == "linux":
            subprocess.Popen([nome_app], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return f"Applicazione '{nome_app}' avviata in background su Linux."
        else:
            return f"Non so come aprire applicazioni su {sistema}."
    except Exception as e:
        return f"❌ Impossibile aprire '{nome_app}'. Assicurati che sia installata e che il nome sia corretto (o presente nel PATH di sistema). Dettaglio errore: {e}"


@tool
def riproduci_audio_testo(testo: str) -> str:
    """
    Legge un testo ad alta voce usando gli altoparlanti del computer.
    Usa questo tool SOLO quando l'utente ti chiede esplicitamente di "leggere", "parlare", "pronunciare" o "dire ad alta voce".
    Passa come parametro il testo ESATTO e completo che vuoi che venga pronunciato.
    """
    print(f"🗣️ [TOOL: Voce] Sintesi vocale in corso: {testo[:40]}...")
    sistema = get_os()
    try:
        if sistema == "darwin":
            # Su Mac passiamo il testo come argomento della lista, così gestisce in automatico gli apostrofi
            subprocess.Popen(["say", testo])
            return "Testo inviato con successo agli altoparlanti del Mac."
        elif sistema == "windows":
            # Su Windows usiamo PowerShell e "scappiamo" (escape) gli apostrofi per evitare crash
            testo_pulito = testo.replace("'", "''")
            ps_script = f"Add-Type -AssemblyName System.Speech; (New-Object System.Speech.Synthesis.SpeechSynthesizer).Speak('{testo_pulito}')"
            subprocess.Popen(["powershell", "-Command", ps_script])
            return "Testo inviato agli altoparlanti di Windows."
        elif sistema == "linux":
            subprocess.Popen(["spd-say", testo])
            return "Testo inviato agli altoparlanti Linux."
        else:
            return f"Sintesi vocale non supportata su {sistema}."
    except Exception as e:
        return f"Errore durante la riproduzione audio: {e}"
    
    
@tool
def controllo_app_nativa(app_name: str, azione: str) -> str:
    """
    Controlla app native (macOS/Windows/Linux). 
    Esempi: app='Finder', azione='apri cartella documenti' | app='Calendario', azione='mostra eventi'
    """
    import platform
    import subprocess
    sistema = platform.system()
    
    if sistema == "Darwin": # macOS
        script = ""
        if "Calendario" in app_name:
            script = 'tell application "Calendar" to activate'
        elif "Finder" in app_name:
            script = 'tell application "Finder" to open home'
        elif "Mail" in app_name:
            script = 'tell application "Mail" to activate'
        
        if script:
            subprocess.run(["osascript", "-e", script])
            return f"Eseguito AppleScript per {app_name}."
            
    elif sistema == "Linux":
        # Su Linux usiamo xdg-open per le azioni standard
        try:
            if "Finder" in app_name or "File" in app_name:
                subprocess.Popen(["xdg-open", os.path.expanduser("~")])
            elif "Mail" in app_name:
                subprocess.Popen(["xdg-open", "mailto:"])
            elif "Browser" in app_name:
                subprocess.Popen(["xdg-open", "http://google.com"])
            return f"Aperta app predefinita per {app_name} su Linux."
        except Exception as e:
            return f"Errore su Linux: {e}"

    elif sistema == "Windows":
        if "Finder" in app_name or "Explorer" in app_name:
            subprocess.run(["explorer", "."])
        return f"Comando inviato a {app_name} su Windows."

    return f"Sistema {sistema} non supportato per azioni specifiche di {app_name}."
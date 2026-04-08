# tools/icloud_tools.py
import os
import datetime
from imap_tools import MailBox, A
from langchain_core.tools import tool
from imap_tools import MailBox, AND
import caldav


ICLOUD_USER = os.getenv("ICLOUD_EMAIL")
ICLOUD_PASS = os.getenv("ICLOUD_APP_PASSWORD") 

@tool
def leggi_email_icloud(max_risultati: int = 5) -> str:
    """Legge le email ricevute sull'account iCloud dell'utente nelle ultime 2 ore."""
    print("[TOOL: iCloud] Lettura Mail in corso (Ultime 2 ore)...")
    try:
        if not ICLOUD_USER or not ICLOUD_PASS:
            return "Errore: Credenziali iCloud mancanti."
            
        # Calcoliamo l'esatto momento di 2 ore fa (usando l'UTC per sicurezza con imap_tools)
        ora_attuale = datetime.datetime.now(datetime.timezone.utc)
        due_ore_fa = ora_attuale - datetime.timedelta(hours=2)
            
        email_list = []
        email_trovate = 0
        
        # iCloud usa questo server IMAP standard
        with MailBox('imap.mail.me.com').login(ICLOUD_USER, ICLOUD_PASS) as mailbox:
            # fetch() estrae le email. limit=20 dà margine per cercare le ultime arrivate, reverse=True prende le più recenti.
            for msg in mailbox.fetch(limit=20, reverse=True):
                # Filtriamo rigorosamente per le ultime 2 ore
                if msg.date >= due_ore_fa:
                    email_list.append(f"Da: {msg.from_}\nOggetto: {msg.subject}\nData: {msg.date.strftime('%Y-%m-%d %H:%M')}\n")
                    email_trovate += 1
                
                # Fermati se hai raggiunto il massimo richiesto
                if email_trovate >= max_risultati:
                    break
                
        if not email_list:
            return "Nessuna nuova email su iCloud nelle ultime 2 ore."
        return "Ecco le ultime email da iCloud:\n\n" + "\n---\n".join(email_list)
    except Exception as e:
        return f"Errore iCloud Mail: {e}"

@tool
def leggi_calendario_icloud() -> str:
    """Legge i prossimi eventi sul Calendario Apple (iCloud)."""
    print("🍎 [TOOL: iCloud] Lettura Calendario in corso...")
    try:
        client = caldav.DAVClient(
            url="https://caldav.icloud.com/", 
            username=ICLOUD_USER, 
            password=ICLOUD_PASS
        )
        principal = client.principal()
        calendars = principal.calendars()
        
        if not calendars:
            return "Nessun calendario iCloud trovato."
            
        oggi = datetime.datetime.now()
        tra_una_settimana = oggi + datetime.timedelta(days=7)
        
        eventi_list = []
        for calendar in calendars:
            # Cerca eventi da oggi a una settimana
            events = calendar.date_search(start=oggi, end=tra_una_settimana, expand=True)
            for event in events:
                event.load()
                # Estraiamo il titolo dell'evento dal formato vCal
                summary = event.vobject_instance.vevent.summary.value
                inizio = event.vobject_instance.vevent.dtstart.value
                eventi_list.append(f"- {inizio}: {summary}")
                
        if not eventi_list:
            return "Non hai eventi programmati su iCloud per i prossimi 7 giorni."
        return "Eventi iCloud in programma:\n" + "\n".join(eventi_list)
        
    except Exception as e:
        return f"Errore iCloud Calendar: {e}"
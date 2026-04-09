# tools/icloud_tools.py
import os
import datetime
from imap_tools import MailBox
from langchain_core.tools import tool
import caldav

@tool
def leggi_email_icloud(max_risultati: int = 5) -> str:
    """Legge le email ricevute sull'account iCloud dell'utente nelle ultime 2 ore."""
    print("☁️ [TOOL: iCloud] Lettura Mail in corso (Ultime 2 ore)...")
    
    # Carichiamo le credenziali dinamicamente così si aggiornano dalla UI
    icloud_user = os.getenv("ICLOUD_EMAIL")
    icloud_pass = os.getenv("ICLOUD_APP_PASSWORD") 
    
    try:
        if not icloud_user or not icloud_pass:
            return "Errore: Credenziali iCloud mancanti. Impostale dalle Impostazioni."
            
        # Calcoliamo l'esatto momento di 2 ore fa in UTC per imap_tools
        ora_attuale = datetime.datetime.now(datetime.timezone.utc)
        due_ore_fa = ora_attuale - datetime.timedelta(hours=2)
            
        email_list = []
        email_trovate = 0
        
        with MailBox('imap.mail.me.com').login(icloud_user, icloud_pass) as mailbox:
            # limit=20 dà margine per cercare le più recenti, reverse=True prende dall'ultima
            for msg in mailbox.fetch(limit=20, reverse=True):
                # Filtriamo rigorosamente per data
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
    
    icloud_user = os.getenv("ICLOUD_EMAIL")
    icloud_pass = os.getenv("ICLOUD_APP_PASSWORD")
    
    try:
        if not icloud_user or not icloud_pass:
            return "Errore: Credenziali iCloud mancanti. Impostale dalle Impostazioni."

        client = caldav.DAVClient(
            url="https://caldav.icloud.com/", 
            username=icloud_user, 
            password=icloud_pass
        )
        principal = client.principal()
        calendars = principal.calendars()
        
        if not calendars:
            return "Nessun calendario iCloud trovato."
            
        oggi = datetime.datetime.now()
        tra_una_settimana = oggi + datetime.timedelta(days=7)
        
        eventi_grezzi = []
        
        for calendar in calendars:
            try:
                # Cerca eventi da oggi a una settimana
                events = calendar.date_search(start=oggi, end=tra_una_settimana, expand=True)
                for event in events:
                    vevent = event.vobject_instance.vevent
                    # Usiamo hasattr per evitare crash su eventi malformati
                    summary = vevent.summary.value if hasattr(vevent, 'summary') else "Evento Senza Titolo"
                    dtstart = vevent.dtstart.value if hasattr(vevent, 'dtstart') else None
                    
                    if dtstart:
                        eventi_grezzi.append((dtstart, summary))
            except Exception as cal_err:
                # Se un singolo calendario condiviso dà problemi di permessi, lo saltiamo
                print(f"⚠️ Ignorato calendario per errore: {cal_err}")
                continue
                
        if not eventi_grezzi:
            return "Non hai eventi programmati su iCloud per i prossimi 7 giorni."
            
        # 1. Ordiniamo TUTTI gli eventi in modo strettamente cronologico!
        eventi_grezzi.sort(key=lambda x: x[0])
        
        # 2. Formattiamo le date per farle leggere bene all'Agente
        eventi_formattati = []
        for dt, titolo in eventi_grezzi:
            # Distingue tra eventi con orario e quelli che durano tutto il giorno
            if isinstance(dt, datetime.datetime):
                data_str = dt.strftime('%Y-%m-%d %H:%M')
            else:
                data_str = dt.strftime('%Y-%m-%d (Tutto il giorno)')
            eventi_formattati.append(f"- {data_str}: {titolo}")

        return "Eventi iCloud in programma:\n" + "\n".join(eventi_formattati)
        
    except Exception as e:
        return f"Errore iCloud Calendar: {e}"
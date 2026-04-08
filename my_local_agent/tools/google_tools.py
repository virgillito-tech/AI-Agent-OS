#tools/google_tools.py:
import base64
import time
from datetime import datetime, timedelta
import datetime
from email.message import EmailMessage
from googleapiclient.discovery import build
from langchain_core.tools import tool
from tools.google_auth import get_google_credentials

# --- TOOLS PER GMAIL ---

@tool
def leggi_ultime_email(max_risultati: int = 5) -> str:
    """
    Legge le ultime email ricevute sull'account Gmail dell'utente nelle ultime 2 ore.
    Usa questo tool quando l'utente ti chiede di controllare la posta o leggere le email recenti.
    """
    try:
        creds = get_google_credentials()
        service = build('gmail', 'v1', credentials=creds)
        
        # Calcoliamo il timestamp Unix di 2 ore fa per la ricerca nativa di Gmail
        due_ore_fa = int(time.time() - (2 * 3600))
        query_ricerca = f"after:{due_ore_fa}"
        
        # Cerca i messaggi nella Inbox filtrando rigorosamente con la query
        results = service.users().messages().list(
            userId='me', 
            labelIds=['INBOX'], 
            maxResults=max_risultati,
            q=query_ricerca  # Il filtro temporale che evita i timeout
        ).execute()
        
        messages = results.get('messages', [])
        
        if not messages:
            return "Non hai nuovi messaggi nella posta in arrivo nelle ultime 2 ore."
            
        email_list = []
        for msg in messages:
            msg_data = service.users().messages().get(userId='me', id=msg['id'], format='metadata', metadataHeaders=['From', 'Subject']).execute()
            headers = msg_data.get('payload', {}).get('headers', [])
            
            mittente = next((h['value'] for h in headers if h['name'] == 'From'), "Sconosciuto")
            oggetto = next((h['value'] for h in headers if h['name'] == 'Subject'), "Senza Oggetto")
            snippet = msg_data.get('snippet', '')
            
            email_list.append(f"Da: {mittente}\nOggetto: {oggetto}\nEstratto: {snippet}...\n")
            
        return "Ecco le tue ultime email:\n\n" + "\n---\n".join(email_list)
    except Exception as e:
        return f"Errore durante la lettura delle email: {e}"

@tool
def invia_email_google(destinatario: str, oggetto: str, corpo: str) -> str:
    """
    Invia un'email usando l'account Gmail ufficiale dell'utente.
    Usa questo strumento QUANDO l'utente ti chiede di mandare una mail a qualcuno.
    """
    try:
        creds = get_google_credentials()
        service = build('gmail', 'v1', credentials=creds)
        
        message = EmailMessage()
        message.set_content(corpo)
        message['To'] = destinatario
        message['From'] = 'me'
        message['Subject'] = oggetto
        
        encoded_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
        create_message = {'raw': encoded_message}
        
        service.users().messages().send(userId='me', body=create_message).execute()
        return f"Email inviata con successo a {destinatario} tramite la tua casella Gmail."
    except Exception as e:
        return f"Errore durante l'invio dell'email: {e}"

# --- TOOLS PER GOOGLE CALENDAR ---

@tool
def leggi_prossimi_eventi_calendario(max_eventi: int = 5) -> str:
    """
    Legge i prossimi eventi in programma sul Google Calendar dell'utente.
    Usa questo tool quando l'utente chiede quali impegni ha oggi o nei prossimi giorni.
    """
    try:
        creds = get_google_credentials()
        service = build('calendar', 'v3', credentials=creds)
        
        # Ottieni la data e l'ora attuale (formato ISO)
        now = datetime.datetime.utcnow().isoformat() + 'Z'
        
        events_result = service.events().list(calendarId='primary', timeMin=now,
                                              maxResults=max_eventi, singleEvents=True,
                                              orderBy='startTime').execute()
        events = events_result.get('items', [])
        
        if not events:
            return "Non hai nessun evento in programma a breve."
            
        event_list = []
        for event in events:
            start = event['start'].get('dateTime', event['start'].get('date'))
            event_list.append(f"- {start}: {event['summary']}")
            
        return "Ecco i tuoi prossimi appuntamenti:\n" + "\n".join(event_list)
    except Exception as e:
        return f"Errore durante la lettura del calendario: {e}"
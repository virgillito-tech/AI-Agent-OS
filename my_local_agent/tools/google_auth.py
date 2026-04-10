#tools/google_auth.py:
import os.path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

# Definiamo i permessi esatti (SCOPES) di cui l'agente ha bisogno
SCOPES = [
    'https://www.googleapis.com/auth/gmail.modify',       # Per leggere e inviare email
    'https://www.googleapis.com/auth/calendar.events',    # Per leggere e creare eventi
    'https://www.googleapis.com/auth/drive'    # Accesso completo a Drive
]

def get_google_credentials(token_filename='token.json'):
    creds = None
    if os.path.exists(token_filename):
        creds = Credentials.from_authorized_user_file(token_filename, SCOPES)
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
            
        with open(token_filename, 'w') as token:
            token.write(creds.to_json())
            
    return creds

if __name__ == '__main__':
    print("Avvio autenticazione Google...")
    get_google_credentials()
    print("✅ Autenticazione completata! Il file token.json è stato creato.")
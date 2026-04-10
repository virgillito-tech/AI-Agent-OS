# tools/drive_tools.py
import os
import io
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaFileUpload
from langchain_core.tools import tool
from tools.google_auth import get_google_credentials

def _get_drive_service():
    """Recupera le credenziali dal tuo gestore centralizzato e avvia il servizio Drive."""
    creds = get_google_credentials()
    return build('drive', 'v3', credentials=creds)

@tool
def esplora_google_drive(query: str = "", max_results: int = 10) -> str:
    """
    Cerca e lista i file su Google Drive. 
    Se 'query' è vuota, mostra gli ultimi file modificati.
    Passa una parola chiave in 'query' per cercare file specifici (es. 'manga', 'fatture').
    """
    print(f"☁️ [TOOL: Drive] Ricerca in corso: '{query}'...")
    try:
        service = _get_drive_service()
        
        q = f"name contains '{query}' and trashed = false" if query else "trashed = false"
        
        results = service.files().list(
            q=q,
            pageSize=max_results, 
            fields="nextPageToken, files(id, name, mimeType, modifiedTime)",
            orderBy="modifiedTime desc"
        ).execute()
        
        items = results.get('files', [])

        if not items:
            return f"Nessun file trovato su Google Drive con la ricerca: '{query}'."
            
        lista_file = []
        for item in items:
            lista_file.append(f"- Nome: {item['name']} | ID: {item['id']} | Tipo: {item['mimeType']}")
            
        return f"Ecco i file trovati su Google Drive:\n\n" + "\n".join(lista_file)
        
    except Exception as e:
        return f"❌ Errore Google Drive: {e}"

@tool
def scarica_da_drive(file_id: str, nome_destinazione: str) -> str:
    """
    Scarica un file specifico da Google Drive sul computer locale.
    Richiede il 'file_id' esatto (ottenibile con esplora_google_drive).
    I file vengono salvati automaticamente nella cartella 'sandbox/'.
    """
    print(f"☁️ [TOOL: Drive] Download file ID: {file_id}...")
    try:
        service = _get_drive_service()
        request = service.files().get_media(fileId=file_id)
        
        os.makedirs("sandbox", exist_ok=True)
        percorso_finale = os.path.join("sandbox", nome_destinazione)
        
        fh = io.FileIO(percorso_finale, 'wb')
        downloader = MediaIoBaseDownload(fh, request)
        
        done = False
        while done is False:
            status, done = downloader.next_chunk()
            
        return f"✅ File scaricato con successo da Drive e salvato qui: {percorso_finale}"
        
    except Exception as e:
        if "fileNotDownloadable" in str(e):
             return f"⚠️ Questo file è un documento Google nativo (Docs/Sheets). Al momento il tool scarica solo file fisici (PDF, immagini, zip, ecc.)."
        return f"❌ Errore download da Drive: {e}"

@tool
def carica_su_drive(percorso_locale: str) -> str:
    """
    Carica un file dal computer locale al tuo Google Drive.
    Passa il percorso assoluto o relativo del file da caricare.
    """
    print(f"☁️ [TOOL: Drive] Upload file: {percorso_locale}...")
    try:
        if not os.path.exists(percorso_locale):
            return f"Errore: Il file {percorso_locale} non esiste sul computer."
            
        service = _get_drive_service()
        nome_file = os.path.basename(percorso_locale)
        
        file_metadata = {'name': nome_file}
        media = MediaFileUpload(percorso_locale, resumable=True)
        
        file = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
        
        return f"✅ File {nome_file} caricato con successo su Google Drive! ID: {file.get('id')}"
        
    except Exception as e:
        return f"❌ Errore upload su Drive: {e}"
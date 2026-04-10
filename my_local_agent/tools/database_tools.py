# tools/database_tools.py
import sqlite3
import os
from langchain_core.tools import tool

# Path al database locale
DB_PATH = os.path.join("sandbox", "ai_os_database.db")

@tool
def gestisci_database_sqlite(query_sql: str) -> str:
    """
    Esegue una query SQL su un database SQLite locale.
    Usa questo tool per creare tabelle, inserire dati o estrarre informazioni strutturate.
    Devi passare una query SQL valida e completa nel parametro 'query_sql'.
    """
    print(f"🗄️ [TOOL: Database] Esecuzione query: {query_sql[:50]}...")
    os.makedirs("sandbox", exist_ok=True)
    
    try:
        # Connettiti al database (lo crea automaticamente se non esiste)
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute(query_sql)
        
        # Se è una query di selezione (SELECT), recupera i risultati
        if query_sql.strip().upper().startswith("SELECT"):
            rows = cursor.fetchall()
            
            # Recupera anche i nomi delle colonne per dare un contesto migliore all'AI
            nomi_colonne = [description[0] for description in cursor.description]
            
            conn.commit()
            conn.close()
            
            if not rows:
                return "La query è stata eseguita, ma non ha restituito alcun risultato."
            
            # Formatta i risultati 
            risultati = f"Colonne: {', '.join(nomi_colonne)}\n"
            risultati += "\n".join([str(row) for row in rows])
            return f"✅ Risultati della query:\n{risultati}"
        
        # Per query strutturali o di modifica (INSERT, UPDATE, DELETE, CREATE)
        else:
            conn.commit()
            righe_modificate = cursor.rowcount
            conn.close()
            return f"✅ Query eseguita con successo. Righe modificate: {righe_modificate}"
            
    except Exception as e:
        return f"❌ Errore durante l'esecuzione della query SQL: {e}"
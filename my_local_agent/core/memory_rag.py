# core/memory_rag.py
import os
from langchain_ollama import OllamaEmbeddings
from langchain_qdrant import QdrantVectorStore
from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, VectorParams

print("🧠 [MEMORY] Modulo Database Vettoriale caricato.")

# Impostiamo la cartella dove Qdrant salverà fisicamente i "ricordi"
DB_PATH = os.path.join("qdrant_db")
os.makedirs(DB_PATH, exist_ok=True)
COLLECTION_NAME = "personal_memory"

# Il modello nomic-embed-text genera vettori di 768 dimensioni
VECTOR_SIZE = 768

def get_vector_store():
    """
    Inizializza il client e l'embedding nel thread corrente.
    Questo bypassa completamente l'errore di Thread-Safety di SQLite!
    """
    # Inizializza il client Qdrant in modalità locale (salvataggio su file)
    client = QdrantClient(path=DB_PATH)
    
    # Crea la collezione se non esiste
    if not client.collection_exists(COLLECTION_NAME):
        print("🧠 [MEMORY] Creazione nuova collezione di memoria...")
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
        )
        
    # Inizializziamo il modello che traduce le parole in vettori
    embeddings = OllamaEmbeddings(model="nomic-embed-text")
    
    # Creiamo l'oggetto VectorStore di LangChain
    return QdrantVectorStore(
        client=client,
        collection_name=COLLECTION_NAME,
        embedding=embeddings,
    )

def add_memory(text: str) -> str:
    """Salva un'informazione a lungo termine."""
    try:
        vs = get_vector_store()
        vs.add_texts([text])
        return f"Ricordo salvato permanentemente: '{text}'"
    except Exception as e:
        print(f"❌ [DEBUG MEMORIA] Errore esatto: {e}")
        return f"Errore nel salvataggio della memoria: {e}"

def retrieve_memory(query: str, k: int = 3) -> str:
    """Cerca nel database i ricordi più simili alla domanda."""
    try:
        vs = get_vector_store()
        results = vs.similarity_search(query, k=k)
        if not results:
            return "Nessun ricordo pertinente trovato nella memoria a lungo termine."
        
        memories = [f"- {res.page_content}" for res in results]
        return "Informazioni recuperate dalla memoria:\n" + "\n".join(memories)
    except Exception as e:
        return f"Errore nel recupero della memoria: {e}"
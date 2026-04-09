# core/memory_rag.py
import os
import config
from langchain_qdrant import QdrantVectorStore
from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, VectorParams

print("🧠 [MEMORY] Modulo Database Vettoriale caricato.")

# Impostiamo la cartella dove Qdrant salverà fisicamente i "ricordi"
DB_PATH = os.path.join("qdrant_db")
os.makedirs(DB_PATH, exist_ok=True)
COLLECTION_NAME = "personal_memory"

# Sia nomic-embed-text che il modello HuggingFace che useremo hanno 768 dimensioni
VECTOR_SIZE = 768

def get_vector_store():
    """
    Inizializza il client e l'embedding in base al motore attivo.
    """
    client = QdrantClient(path=DB_PATH)
    motore_attivo = getattr(config, "ACTIVE_ENGINE", "ollama")
    
    if motore_attivo == "ollama":
        from langchain_ollama import OllamaEmbeddings
        embeddings = OllamaEmbeddings(model="nomic-embed-text")
    else:
        # Quando siamo su MLX, usiamo un modello Python locale accelerato su Apple Silicon
        from langchain_huggingface import HuggingFaceEmbeddings
        # Questo modello è eccellente per l'italiano e spara vettori a 768 dimensioni
        embeddings = HuggingFaceEmbeddings(
            model_name="sentence-transformers/paraphrase-multilingual-mpnet-base-v2",
            model_kwargs={'device': 'mps'} # Usa la GPU unificata del Mac
        )
    
    # Crea la collezione se non esiste
    if not client.collection_exists(COLLECTION_NAME):
        print(f"🧠 [MEMORY] Creazione collezione ({motore_attivo} mode)...")
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
        )
        
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
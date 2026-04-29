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
CHAT_HISTORY_COLLECTION = "chat_history"
DOCUMENTS_COLLECTION = "local_documents"

VECTOR_SIZE = 768

def get_embeddings():
    motore_attivo = getattr(config, "ACTIVE_ENGINE", "ollama")
    if motore_attivo == "ollama":
        from langchain_ollama import OllamaEmbeddings
        return OllamaEmbeddings(model="nomic-embed-text")
    else:
        from langchain_huggingface import HuggingFaceEmbeddings
        return HuggingFaceEmbeddings(
            model_name="sentence-transformers/paraphrase-multilingual-mpnet-base-v2",
            model_kwargs={'device': 'mps'}
        )

def _init_collection(client: QdrantClient, name: str):
    if not client.collection_exists(name):
        print(f"🧠 [MEMORY] Creazione collezione '{name}' in Qdrant...")
        client.create_collection(
            collection_name=name,
            vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
        )

def get_vector_store(collection_name: str = COLLECTION_NAME):
    client = QdrantClient(path=DB_PATH)
    embeddings = get_embeddings()
    _init_collection(client, collection_name)
        
    return QdrantVectorStore(
        client=client,
        collection_name=collection_name,
        embedding=embeddings,
    )

def add_memory(text: str) -> str:
    """Salva un'informazione a lungo termine."""
    try:
        vs = get_vector_store(COLLECTION_NAME)
        vs.add_texts([text])
        return f"Ricordo salvato permanentemente: '{text}'"
    except Exception as e:
        print(f"❌ [DEBUG MEMORIA] Errore esatto: {e}")
        return f"Errore nel salvataggio della memoria: {e}"

def retrieve_memory(query: str, k: int = 3) -> str:
    """Cerca nel database i ricordi più simili alla domanda."""
    try:
        vs = get_vector_store(COLLECTION_NAME)
        results = vs.similarity_search(query, k=k)
        if not results:
            return "Nessun ricordo pertinente trovato nella memoria a lungo termine."
        
        memories = [f"- {res.page_content}" for res in results]
        return "Informazioni recuperate dalla memoria:\n" + "\n".join(memories)
    except Exception as e:
        return f"Errore nel recupero della memoria: {e}"

def add_chat_history(text: str) -> bool:
    """Salva vecchi messaggi della chat per context retrieval."""
    try:
        vs = get_vector_store(CHAT_HISTORY_COLLECTION)
        vs.add_texts([text])
        return True
    except Exception as e:
        print(f"❌ [DEBUG CHAT_HISTORY] Errore salvataggio: {e}")
        return False

def retrieve_chat_history(query: str, k: int = 5) -> str:
    """Recupera la cronologia passata della chat in base alla similarità."""
    try:
        vs = get_vector_store(CHAT_HISTORY_COLLECTION)
        results = vs.similarity_search(query, k=k)
        if not results:
            return ""
        return "\n".join([res.page_content for res in results])
    except Exception as e:
        return ""
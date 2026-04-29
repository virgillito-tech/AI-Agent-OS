import os
from langchain_text_splitters import RecursiveCharacterTextSplitter
from core.memory_rag import get_vector_store, DOCUMENTS_COLLECTION

def index_local_document(file_path: str) -> str:
    """Legge, fa chunking e vettorizza un singolo documento."""
    path_reale = os.path.expanduser(file_path)
    if not os.path.exists(path_reale):
        return f"File non trovato: {path_reale}"
        
    estensione = os.path.splitext(path_reale)[1].lower()
    testo_completo = ""
    
    try:
        if estensione == '.pdf':
            import pypdf
            with open(path_reale, "rb") as f:
                reader = pypdf.PdfReader(f)
                for page in reader.pages:
                    testo = page.extract_text()
                    if testo:
                        testo_completo += testo + "\n"
        elif estensione in ['.txt', '.md', '.csv', '.json', '.py', '.js', '.html']:
            with open(path_reale, "r", encoding="utf-8") as f:
                testo_completo = f.read()
        else:
            return f"Formato non supportato: {estensione}"
            
        if not testo_completo.strip():
            return f"Nessun testo estraibile in: {path_reale}"
            
        # Chunking: dividiamo in pezzi da 1000 caratteri con 200 di overlap
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            length_function=len,
        )
        
        chunks = text_splitter.split_text(testo_completo)
        
        # Aggiungiamo i metadati ai chunks per capire da dove vengono
        metadatas = [{"source": path_reale} for _ in chunks]
        
        vs = get_vector_store(DOCUMENTS_COLLECTION)
        vs.add_texts(texts=chunks, metadatas=metadatas)
        
        return f"Indicizzato '{os.path.basename(path_reale)}': {len(chunks)} frammenti aggiunti al database."
        
    except Exception as e:
        return f"Errore indicizzazione {path_reale}: {e}"

def index_directory(dir_path: str) -> str:
    """Indicizza in blocco tutti i documenti compatibili in una cartella."""
    path_reale = os.path.expanduser(dir_path)
    if not os.path.isdir(path_reale):
        return f"La cartella {path_reale} non esiste."
        
    print(f"📚 [RAG] Avvio indicizzazione cartella: {path_reale}")
    risultati = []
    file_processati = 0
    
    # Esplorazione ricorsiva
    for root, _, files in os.walk(path_reale):
        for file in files:
            if not file.startswith('.'): # Ignoriamo i file nascosti
                ext = os.path.splitext(file)[1].lower()
                if ext in ['.pdf', '.txt', '.md', '.csv']:
                    file_path = os.path.join(root, file)
                    res = index_local_document(file_path)
                    if "Indicizzato" in res:
                        file_processati += 1
                    risultati.append(res)
                    
    print(f"📚 [RAG] Completata indicizzazione di {file_processati} file.")
    return f"Indicizzazione completata. File processati con successo: {file_processati}.\nDettagli:\n" + "\n".join(risultati[:10]) + ("\n..." if len(risultati)>10 else "")

def retrieve_document_context(query: str, k: int = 5) -> str:
    """Cerca le informazioni nei documenti vettorializzati."""
    try:
        vs = get_vector_store(DOCUMENTS_COLLECTION)
        results = vs.similarity_search(query, k=k)
        if not results:
            return "Nessuna informazione rilevante trovata nei documenti locali."
        
        docs = [f"[File: {res.metadata.get('source', 'Sconosciuto')}]\n{res.page_content}" for res in results]
        return "Risultati trovati nei tuoi documenti:\n\n" + "\n\n---\n\n".join(docs)
    except Exception as e:
        return f"Errore ricerca documenti: {e}"

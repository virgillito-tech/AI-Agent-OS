# main.py
import os
import sys

import ctypes

# --- KILL DEFINITIVO MALLOC LOGGING (LIVELLO C) ---
def disable_macos_malloc_logging():
    if sys.platform == "darwin":
        try:
            libc = ctypes.CDLL(None)
            unsetenv = libc.unsetenv
            unsetenv.argtypes = [ctypes.c_char_p]
            unsetenv(b"MALLOC_STACK_LOGGING")
        except Exception:
            pass
    # Rimuoviamo invece di impostare a "0" per evitare il log di errore in subprocess
    os.environ.pop("MALLOC_STACK_LOGGING", None)

disable_macos_malloc_logging()

import multiprocessing
if __name__ == '__main__':
    multiprocessing.freeze_support()

import re
import shutil

# Le app GUI del Mac non sanno dove siano i programmi. Glielo diciamo noi!
os.environ["PATH"] += os.pathsep + "/usr/local/bin" + os.pathsep + "/opt/homebrew/bin"

# PyInstaller: se avviato come eseguibile, sposta la cartella prompts
if getattr(sys, 'frozen', False):
    base_path = sys._MEIPASS
    src_prompts = os.path.join(base_path, "prompts")
    dst_prompts = os.path.join(os.getcwd(), "prompts")
    if os.path.exists(src_prompts) and not os.path.exists(dst_prompts):
        shutil.copytree(src_prompts, dst_prompts)

from dotenv import load_dotenv
load_dotenv()

# Forza il token di HuggingFace per mlx_lm e transformers
if "HF_TOKEN" in os.environ and "HUGGING_FACE_HUB_TOKEN" not in os.environ:
    os.environ["HUGGING_FACE_HUB_TOKEN"] = os.environ["HF_TOKEN"]

# Silenzia i report "UNEXPECTED" di sentence-transformers e i warning di HuggingFace
import logging
logging.getLogger("sentence_transformers").setLevel(logging.ERROR)
logging.getLogger("transformers").setLevel(logging.ERROR)
logging.getLogger("huggingface_hub").setLevel(logging.ERROR)

# Carica le variabili d'ambiente direttamente dalla cartella di progetto
load_dotenv(".env")

from pydantic import BaseModel
import tempfile
import psutil
import httpx
import uuid
import json
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, File, UploadFile, Form
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from fastapi.middleware.cors import CORSMiddleware
from faster_whisper import WhisperModel
from fastapi.responses import StreamingResponse

from core.listener import avvia_listener
import config
from core.model_manager import start_engine, stop_engine
from agents.core_agent import get_agent_executor, get_dynamic_system_prompt, delegato_comunicazioni
from core.llm_factory import get_llm
from core.scheduler import avvia_scheduler

# --- GESTIONE STORIA GLOBALE ---
GLOBAL_HISTORY_FILE = "sandbox/global_chat_history.json"

from core.shared import ai_lock
from core.stats import gpu_polling_loop, get_gpu_percent
from core.daemon import esegui_controllo_guardiano
from core.scheduler import scheduler




@asynccontextmanager
async def lifespan(app: FastAPI):
    avvia_scheduler()
    
    # Scheduliamo il guardiano ogni 30 minuti in un MemoryJobStore provvisorio
    try:
        scheduler.add_job(esegui_controllo_guardiano, 'interval', minutes=30, id='daemon_guardiano', replace_existing=True)
        print("🛡️ [GUARDIANO] Schedulato correttamente ogni 30 minuti via apscheduler.")
    except Exception as e:
        print(f"Errore schedulazione guardiano: {e}")
        
    avvia_listener()
    asyncio.create_task(gpu_polling_loop())
    yield

app = FastAPI(title="Local AI Agent OS", version="1.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

os.makedirs("temp_uploads", exist_ok=True)
os.makedirs("sandbox", exist_ok=True)

print("Caricamento modello Whisper...")
whisper_model = WhisperModel("base", device="auto")
print("Whisper pronto!")

@app.get("/api/setup/health")
async def health_check():
    from core.model_manager import is_ollama_running
    return {"ollama_active": is_ollama_running(), "workspace_granted": os.path.exists("sandbox")}

@app.post("/api/setup/workspace")
async def set_workspace(data: dict):
    path = data.get("path", "sandbox")
    os.makedirs(path, exist_ok=True)
    with open(".workspace_path", "w") as f:
        f.write(path)
    return {"status": "ok"}

@app.get("/api/system_stats")
async def get_system_stats():
    try:
        cpu = psutil.cpu_percent(interval=0.1)
        ram = psutil.virtual_memory()
        
        # Calcoliamo i valori una volta sola
        total_gb = round(ram.total / (1024 ** 3), 1)
        used_gb = round(ram.used / (1024 ** 3), 1)
        percent = ram.percent
        
        return {
            # Formato standard (quello che hai ora)
            "cpu_percent": cpu,
            "ram_percent": percent,
            "ram_used_gb": used_gb,
            "ram_total_gb": total_gb,
            
            # Formati alternativi (per compatibilità frontend)
            "cpuPercent": cpu,
            "ramPercent": percent,
            "ramUsed": used_gb,
            "ramTotal": total_gb,
            "gpu_percent": get_gpu_percent()
        }
    except Exception as e:
        return {"error": str(e)}

@app.post("/api/system/clear_cache")
async def clear_system_cache():
    """Forza il garbage collector e pulisce la memoria MLX per liberare VRAM."""
    import gc
    gc.collect()
    motore = getattr(config, "ACTIVE_ENGINE", "ollama")
    if motore == "mlx" and sys.platform == "darwin":
        try:
            import mlx.core as mx
            mx.metal.clear_cache()
            return {"status": "ok", "message": "Cache MLX e GC puliti con successo."}
        except ImportError:
            pass
    return {"status": "ok", "message": "Garbage Collector eseguito."}

@app.get("/api/settings/permissions")
async def get_permissions():
    return {"allow_global_write": config.ALLOW_GLOBAL_WRITE}

@app.post("/api/settings/permissions")
async def set_permissions(data: dict):
    allow = data.get("allow_global_write", False)
    config.ALLOW_GLOBAL_WRITE = allow
    return {"status": "ok", "allow_global_write": config.ALLOW_GLOBAL_WRITE}

class EnvSettings(BaseModel):
    TELEGRAM_TOKEN: str = ""
    TG_API_ID: str = ""
    TG_API_HASH: str = ""
    EMAIL_USER: str = ""
    EMAIL_PASSWORD: str = ""
    ICLOUD_EMAIL: str = ""
    ICLOUD_APP_PASSWORD: str = ""
    SANDBOX_DIR: str = "sandbox"
    IMAGE_GEN_API_URL: str = "http://localhost:8000/generate"
    IMAGE_MODEL_NAME: str = "flux"
    ACTIVE_ENGINE: str = "ollama"
    TEXT_MODEL_NAME: str = ""
    FAST_MODEL_NAME: str = ""
    BASE_URL_TEXT: str = "http://localhost:11434"
    VISION_MODEL_NAME: str = ""
    BASE_URL_VISION: str = "http://localhost:11434"
    MAX_TOKENS: str = "4096"
    MLX_TEXT_MODEL_NAME: str = ""
    MLX_BASE_URL: str = "http://localhost:8080"
    MLX_VISION_MODEL_NAME: str = ""
    MLX_FAST_MODEL_NAME: str = ""
    VIDEO_MODEL_NAME: str = "THUDM/CogVideoX-2b"
    VIDEO_DEVICE: str = "auto"

@app.get("/api/settings/env")
async def get_env_settings():
    env_path = ".env"
    settings = EnvSettings().model_dump()
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                if "=" in line and not line.strip().startswith("#"):
                    k, v = line.strip().split("=", 1)
                    if k in settings:
                        settings[k] = v.strip("'\"")
    return settings

@app.post("/api/settings/env")
async def save_env_settings(data: EnvSettings):
    env_path = ".env"
    with open(env_path, "w", encoding="utf-8") as f:
        for k, v in data.model_dump().items():
            f.write(f"{k}={v}\n")
    load_dotenv(env_path, override=True)
    return {"status": "ok"}

def get_global_history():
    if not os.path.exists(GLOBAL_HISTORY_FILE):
        return []
    try:
        with open(GLOBAL_HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return []

def add_to_global_history(role: str, content: str, source: str = "web"):
    history = get_global_history()
    msg_id = str(uuid.uuid4())
    history.append({"id": msg_id, "role": role, "content": content, "source": source})
    history = history[-50:]
    with open(GLOBAL_HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2, ensure_ascii=False)

async def compatta_cronologia_se_necessario():
    history = get_global_history()
    # Quando superiamo i 15 messaggi, i più vecchi finiscono nella memoria a lungo termine
    if len(history) > 15:
        from core.memory_rag import add_chat_history
        da_archiviare = history[:-8] # Manteniamo gli ultimi 8 intatti
        da_mantenere = history[-8:]
        
        # Salviamo i messaggi espulsi nel RAG vettoriale
        for msg in da_archiviare:
            if msg.get("role") != "system" and not msg.get("content").startswith("[RIASSUNTO"):
                testo = f"{msg['role'].upper()}: {msg['content']}"
                add_chat_history(testo)
                
        # Semplicemente tronchiamo la history attiva, senza pesare sull'LLM per il riassunto
        with open(GLOBAL_HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(da_mantenere, f, indent=2, ensure_ascii=False)

@app.get("/api/history")
async def api_get_history():
    return get_global_history()

@app.post("/api/history/clear")
async def api_clear_history():
    if os.path.exists(GLOBAL_HISTORY_FILE):
        os.remove(GLOBAL_HISTORY_FILE)
    return {"status": "ok"}

def build_langchain_messages_from_global(): 
    sys_prompt = get_dynamic_system_prompt()
    
    # RAG INJECTION: Cerchiamo messaggi rilevanti dal passato se ci sono domande dell'utente
    history = get_global_history()
    user_msgs = [m["content"] for m in history if m.get("role") == "user"]
    context_rag = ""
    if user_msgs:
        ultima_domanda = user_msgs[-1]
        try:
            from core.memory_rag import retrieve_chat_history, retrieve_memory
            
            # 1. Recupero frammenti dalle chat passate
            contesto_recuperato = retrieve_chat_history(ultima_domanda, k=5)
            if contesto_recuperato:
                context_rag += f"\n\n[CONTESTO DA CONVERSAZIONI PASSATE]:\nQuesti sono estratti da conversazioni passate rilevanti per la domanda attuale:\n{contesto_recuperato}\n"
                
            # 2. Recupero identità e dati personali a lungo termine
            memoria_personale = retrieve_memory(ultima_domanda, k=3)
            if "Nessun ricordo pertinente" not in memoria_personale:
                context_rag += f"\n\n[MEMORIA A LUNGO TERMINE (Identità e Fatti)]:\nQueste sono informazioni stabili che sai sull'utente e sul mondo:\n{memoria_personale}\n"
                
            if context_rag:
                context_rag += "\nUsa questo contesto solo se utile a rispondere in modo naturale e discorsivo."
                
        except Exception as e:
            print(f"Errore RAG injection: {e}")
            
    langchain_messages = [SystemMessage(content=sys_prompt + context_rag)]
    for msg in history:
        if msg.get("role") == "user":
            langchain_messages.append(HumanMessage(content=msg["content"]))
        elif msg.get("role") in ["ai", "system"]:
            langchain_messages.append(AIMessage(content=msg["content"]))
    return langchain_messages

@app.get("/api/models")
async def get_available_models(engine: str = "ollama"):
    if engine == "ollama":
        try:
            async with httpx.AsyncClient() as client:
                res = await client.get("http://localhost:11434/api/tags", timeout=2.0)
                if res.status_code == 200:
                    return {"models": [m["name"] for m in res.json().get("models", []) if "embed" not in m["name"].lower()]}
        except:
            return {"models": [], "error": "Ollama non raggiungibile."}
    elif engine == "mlx":
        cache_dir = os.path.expanduser("~/.cache/huggingface/hub")
        downloaded = [d.replace("models--", "").replace("--", "/") for d in os.listdir(cache_dir) if d.startswith("models--")] if os.path.exists(cache_dir) else []
        return {"models": sorted(list(set(["mlx-community/Qwen3.5-9B-MLX-4bit"] + downloaded)))}
    return {"models": []}

@app.post("/api/engine/start")
async def api_start_engine(engine: str = Form(...), model: str = Form(None)):
    model_name = model or config.TEXT_MODEL_NAME
    if engine == "mlx":
        config.MLX_TEXT_MODEL_NAME = model_name
    else:
        config.TEXT_MODEL_NAME = model_name
    success, message = await start_engine(engine_type=engine, model_name=model_name)
    if success:
        config.ACTIVE_ENGINE = engine
    return {"status": "ok" if success else "error", "message": message}

@app.post("/api/engine/stop")
async def api_stop_engine():
    success, message = stop_engine()
    return {"status": "ok" if success else "error", "message": message}

@app.post("/api/transcribe")
async def transcribe_audio(audio: UploadFile = File(...)):
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".webm") as tmp:
            tmp.write(await audio.read())
            tmp_path = tmp.name
        segments, _ = whisper_model.transcribe(tmp_path, beam_size=5, language="it")
        os.remove(tmp_path)
        return {"text": "".join([s.text for s in segments]).strip()}
    except Exception as e:
        return {"error": str(e)}

def _save_upload(file: UploadFile) -> str:
    path = os.path.join("temp_uploads", f"upload_{os.urandom(4).hex()}{os.path.splitext(file.filename or '.bin')[1]}")
    file.file.seek(0)
    with open(path, "wb") as f:
        shutil.copyfileobj(file.file, f)
    return path

# ---------------------------------------------------------------------------
# CHAT STREAMING E SINCRONO
# ---------------------------------------------------------------------------

@app.post("/api/chat")
async def chat_endpoint(
    message: str = Form(...),
    file: UploadFile = File(None),
    engine: str = Form("ollama"),
    mode: str = Form("agent"),
):
    config.ACTIVE_ENGINE = engine
    await compatta_cronologia_se_necessario()

    content_to_save = message
    if file and file.filename:
        file_path = _save_upload(file)
        estensione = os.path.splitext(file.filename)[1].lower()
        if estensione in [".pdf", ".txt", ".md", ".docx", ".csv"]:
            content_to_save += f"\n\n[📂 DOCUMENTO ALLEGATO: {file_path} | REGOLA: USA SUBITO IL TOOL `leggi_documento`.]"
        elif estensione in [".png", ".jpg", ".jpeg", ".webp"]:
            content_to_save += f"\n\n[🖼️ IMMAGINE ALLEGATA: {file_path} | Usa il tool di Visione.]"
        else:
            content_to_save += f"\n\n[📎 FILE ALLEGATO: {file_path}]"
        
    add_to_global_history("user", content_to_save, source="web")
    langchain_messages = build_langchain_messages_from_global()
    
    task_type = "fast" if mode == "fast" else "reasoning"
    agent = await get_agent_executor(task_type=task_type)
    inputs = {"messages": langchain_messages}

    async def event_generator():
        async with ai_lock: 
            try:
                yield f"data: {json.dumps({'type': 'status', 'content': '🧠 Avvio sistema cognitivo...'})}\n\n"
                
                final_text = ""
                tool_results_for_fallback = []
                
                async for msg, metadata in agent.astream(inputs, stream_mode="messages"):
                    if msg.type == "ai":
                        if hasattr(msg, "tool_call_chunks") and msg.tool_call_chunks:
                            for tc in msg.tool_call_chunks:
                                tool_name = tc.get("name")
                                if tool_name:
                                    yield f"data: {json.dumps({'type': 'reasoning', 'content': f'🛠️ Avvio strumento: {tool_name}'})}\n\n"
                                    
                        # Gestione dei modelli di ragionamento (R1, QwQ, ecc.)
                        if hasattr(msg, "additional_kwargs") and "reasoning" in msg.additional_kwargs:
                            reasoning_chunk = msg.additional_kwargs["reasoning"]
                            if reasoning_chunk:
                                final_text += reasoning_chunk
                                yield f"data: {json.dumps({'type': 'reasoning', 'content': reasoning_chunk})}\n\n"

                        if msg.content:
                            if isinstance(msg.content, str):
                                final_text += msg.content
                                yield f"data: {json.dumps({'type': 'chunk', 'content': msg.content})}\n\n"
                            elif isinstance(msg.content, list):
                                for block in msg.content:
                                    if isinstance(block, dict) and "text" in block:
                                        final_text += block["text"]
                                        yield f"data: {json.dumps({'type': 'chunk', 'content': block['text']})}\n\n"
                            
                    elif msg.type == "tool":
                        tool_results_for_fallback.append(f"Tool [{msg.name}] ha risposto: {msg.content}")
                        yield f"data: {json.dumps({'type': 'reasoning', 'content': f'✅ Dati estratti da {msg.name}. Elaboro...'})}\n\n"

                # --- INIZIO DOPPIO MOTORE (ROUTER ANTI-BUG) ---
                if not final_text.strip():
                    # FIX: Temp 0.6 sveglia il modello e gli impedisce di allucinare spazi vuoti infiniti
                    llm_fallback = await get_llm(task_type="fast", temperature=0.6)
                    empty_chunks = 0 # Contatore della ghigliottina anti-spazio
                    
                    chat_messages = build_langchain_messages_from_global()
                    
                    if tool_results_for_fallback:
                        yield f"data: {json.dumps({'type': 'reasoning', 'content': '🧠 Rielaborazione dati in corso...'})}\n\n"
                        testi_estratti = "\n".join(tool_results_for_fallback)
                        chat_messages.append(HumanMessage(content=f"Dati estratti dai tool:\n{testi_estratti}\n\nUsa questi dati per rispondere all'ultima domanda."))
                    else:
                        yield f"data: {json.dumps({'type': 'reasoning', 'content': '🧠 Conversazione in corso...'})}\n\n"
                        
                    async for chunk in llm_fallback.astream(chat_messages):
                            reasoning_chunk = chunk.additional_kwargs.get("reasoning", "") if hasattr(chunk, "additional_kwargs") else ""
                            if reasoning_chunk:
                                empty_chunks = 0  # Resetta se sta ragionando
                                final_text += reasoning_chunk
                                yield f"data: {json.dumps({'type': 'reasoning', 'content': reasoning_chunk})}\n\n"
                                
                            if chunk.content:
                                # Ghigliottina Anti-Spazio
                                if not chunk.content.strip():
                                    empty_chunks += 1
                                    if empty_chunks > 50: break
                                else:
                                    empty_chunks = 0
                                final_text += chunk.content
                                yield f"data: {json.dumps({'type': 'chunk', 'content': chunk.content})}\n\n"
                # --- FINE DOPPIO MOTORE ---

                yield f"data: {json.dumps({'type': 'status', 'content': '✍️ Scrittura completata.'})}\n\n"
                
                if not final_text.strip():
                    final_text = "Ho processato la tua richiesta correttamente, ma non ci sono dati testuali da aggiungere."
                    yield f"data: {json.dumps({'type': 'chunk', 'content': final_text})}\n\n"

                add_to_global_history("ai", final_text, source="web")
                yield f"data: {json.dumps({'type': 'final'})}\n\n"

            except Exception as e:
                yield f"data: {json.dumps({'type': 'error', 'content': f'Errore critico: {str(e)}'})}\n\n"
            yield "data: [DONE]\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")

@app.post("/api/chat/sync")
async def chat_sync_endpoint(
    message: str = Form(...),
    mode: str = Form("agent"),
    engine: str = Form("ollama")
):
    config.ACTIVE_ENGINE = engine
    await compatta_cronologia_se_necessario()
    try:
        add_to_global_history("user", message, source="telegram")
        
        task_type = "fast" if mode == "fast" else "reasoning"
        agent = await get_agent_executor(task_type=task_type)
        langchain_messages = build_langchain_messages_from_global()
        
        async with ai_lock: 
            inputs = {"messages": langchain_messages}
            result = await agent.ainvoke(inputs)
        
        final_message = ""
        tool_results_for_fallback = []
        
        if result and "messages" in result:
            messages = result["messages"]
            for msg in reversed(messages):
                if msg.type == "ai" and not getattr(msg, "tool_calls", None) and msg.content:
                    final_message = msg.content
                    break
            
            if not final_message:
                for msg in messages:
                    if msg.type == "tool":
                        tool_results_for_fallback.append(f"[{msg.name}]: {msg.content}")
                
                # Applichiamo l'anti-bug anche in Sync
                llm_fallback = await get_llm(task_type="fast", temperature=0.6)
                empty_chunks = 0
                
                chat_messages = build_langchain_messages_from_global()
                
                if tool_results_for_fallback:
                    testi_estratti = "\n".join(tool_results_for_fallback)
                    chat_messages.append(HumanMessage(content=f"Dati estratti dai tool:\n{testi_estratti}\n\nUsa questi dati per rispondere all'ultima domanda."))
                
                async for chunk in llm_fallback.astream(chat_messages):
                        if chunk.content:
                            if not chunk.content.strip():
                                empty_chunks += 1
                                if empty_chunks > 10: break
                            else:
                                empty_chunks = 0
                            final_message += chunk.content
                        
        if not final_message:
            final_message = "Azione eseguita."
            
        add_to_global_history("ai", final_message, source="telegram")
            
        return {"response": final_message, "status": "ok"}
    except Exception as e:
        return {"response": f"Errore interno: {str(e)}", "status": "error"}

if __name__ == "__main__":
    import uvicorn
    port = 8000
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except:
            pass
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")
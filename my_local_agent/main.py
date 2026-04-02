# main.py
import multiprocessing

if __name__ == '__main__':
    multiprocessing.freeze_support()

import os
import re
import sys
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

_gpu_percent: float = 0.0

# --- IL GUARDIANO PROATTIVO (DAEMON) ---
async def proactive_guardian_loop():
    print("🛡️ [GUARDIANO] Inizializzato. In attesa del primo ciclo (30s)...")
    await asyncio.sleep(30)
    
    while True:
        try:
            chat_id_path = os.path.join("sandbox", "tg_chat_id.txt")
            
            if not os.path.exists(chat_id_path):
                print("🛡️ [GUARDIANO] ⚠️ File tg_chat_id.txt non trovato. Mandami un messaggio dal tuo telefono su Telegram per attivarmi!")
            else:
                with open(chat_id_path, "r") as f:
                    chat_id = f.read().strip()
                
                print("\n🛡️ [GUARDIANO] Risveglio: Estrazione dati in background...")
                
                # 1. ESECUZIONE DIRETTA DEI TOOL
                from tools.agent_tools import leggi_tutte_le_chat
                from tools.google_tools import leggi_ultime_email
                from tools.icloud_tools import leggi_email_icloud
                
                loop = asyncio.get_event_loop()
                
                # Estraiamo Gmail
                try:
                    gmail_text = await loop.run_in_executor(None, leggi_ultime_email.invoke, {})
                except Exception as e:
                    gmail_text = f"Errore lettura Gmail: {e}"

                # Estraiamo iCloud Mail
                try:
                    icloud_text = await loop.run_in_executor(None, leggi_email_icloud.invoke, {})
                except Exception as e:
                    icloud_text = f"Errore lettura iCloud: {e}"
                
                # Estraiamo le chat
                try:
                    chat_text = await loop.run_in_executor(None, leggi_tutte_le_chat.invoke, {})
                except Exception as e:
                    chat_text = f"Errore lettura chat: {e}"
                
                # Uniamo TUTTO in un unico mega-blocco di testo freddo
                blocco_testo = f"=== GMAIL ===\n{gmail_text}\n\n=== ICLOUD ===\n{icloud_text}\n\n=== CHAT ===\n{chat_text}"
                
                # 2. CARICHIAMO LA "COSTITUZIONE" DEL GUARDIANO
                prompt_path = os.path.join("prompts", "tiny_model.md")
                try:
                    with open(prompt_path, "r", encoding="utf-8") as f:
                        tiny_prompt = f.read()
                except FileNotFoundError:
                    tiny_prompt = "Trova urgenze. Altrimenti scrivi NESSUNA_URGENZA."
                
                # 3. CHIAMATA DIRETTA E PURA AL LLM
                llm = await get_llm(task_type="fast", temperature=0.0)
                res = await llm.ainvoke([
                    SystemMessage(content=tiny_prompt),
                    HumanMessage(content=blocco_testo)
                ])
                
                testo_risposta = res.content.strip()
                print(f"🛡️ [DEBUG GUARDIANO] Analisi cruda del LLM: {testo_risposta}")
                
                # 4. CONTROLLO ALLARME PIÙ ROBUSTO
                testo_check = testo_risposta.upper()
                
                # Lista di parole "sicure", incluse le storpiature tipiche
                parole_sicure = ["NESSUNA_URGENZA", "NESSUN", "NESSEM", "NO_URGENZA", "NESSUNA URGENZA"]
                
                if not any(safe_word in testo_check for safe_word in parole_sicure):
                    print(f"🛡️ [GUARDIANO] 🚨 Urgenza rilevata! Invio notifica push a Telegram...")
                    token = os.getenv("TELEGRAM_TOKEN")
                    
                    if not token:
                        print("🛡️ [GUARDIANO] ❌ ERRORE: TELEGRAM_TOKEN non trovato.")
                    else:
                        url = f"https://api.telegram.org/bot{token}/sendMessage"
                        testo_notifica = f"🚨 *AI OS | Notifica Proattiva:*\n\n{testo_risposta}"
                        data = {"chat_id": chat_id, "text": testo_notifica, "parse_mode": "Markdown"}
                        async with httpx.AsyncClient() as client:
                            resp = await client.post(url, data=data)
                            if resp.status_code == 200:
                                print("🛡️ [GUARDIANO] ✅ Notifica push inviata con successo!")
                            else:
                                print(f"🛡️ [GUARDIANO] ❌ Errore API Telegram: {resp.text}")
                else:
                    print("🛡️ [GUARDIANO] 🟢 Nessuna urgenza rilevata. Torno a dormire.")
                    
        except Exception as e:
            print(f"🛡️ [GUARDIANO] ❌ Errore critico nel loop: {e}")
        
        # Dorme per 30 minuti (1800 secondi)
        await asyncio.sleep(1800)

async def _gpu_polling_loop():
    global _gpu_percent
    import platform
    import asyncio
    import re
    
    sistema = platform.system().lower()
    
    while True:
        try:
            if sistema == "darwin":
                # --- LOGICA MAC (Apple Silicon) ---
                proc = await asyncio.create_subprocess_exec(
                    "sudo", "-n", "powermetrics", "--samplers", "gpu_power", "-n", "1", "-i", "200",
                    stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL,
                )
                stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=3.0)
                m = re.search(r"GPU Active Residency:\s+([\d.]+)%", stdout.decode())
                if m:
                    _gpu_percent = float(m.group(1))
                else:
                    _gpu_percent = 0.0
                    
            else:
                # --- LOGICA WINDOWS / LINUX (NVIDIA) ---
                try:
                    import GPUtil
                    gpus = GPUtil.getGPUs()
                    if gpus:
                        _gpu_percent = gpus[0].load * 100.0
                    else:
                        _gpu_percent = 0.0
                except ImportError:
                    _gpu_percent = 0.0

        except Exception:
            _gpu_percent = 0.0
            
        await asyncio.sleep(5)

@asynccontextmanager
async def lifespan(app: FastAPI):
    avvia_scheduler()
    avvia_listener()
    asyncio.create_task(_gpu_polling_loop())
    asyncio.create_task(proactive_guardian_loop()) 
    yield

app = FastAPI(title="Local AI Agent OS", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
        return {
            "cpu_percent": cpu,
            "ram_percent": ram.percent,
            "ram_used_gb": round(ram.used / (1024 ** 3), 1),
            "ram_total_gb": round(ram.total / (1024 ** 3), 1),
            "gpu_percent": _gpu_percent,
        }
    except Exception as e:
        return {"error": str(e)}

@app.get("/api/settings/permissions")
async def get_permissions():
    return {"allow_global_write": config.ALLOW_GLOBAL_WRITE}

@app.post("/api/settings/permissions")
async def set_permissions(data: dict):
    allow = data.get("allow_global_write", False)
    config.ALLOW_GLOBAL_WRITE = allow
    print(f"🛡️ [SECURITY] Permessi di Scrittura Globali impostati su: {allow}")
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

@app.get("/api/settings/env")
async def get_env_settings():
    env_path = ".env"
    # Inizializza con i valori vuoti/default del modello
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
    # Scrive tutte le variabili in automatico
    with open(env_path, "w", encoding="utf-8") as f:
        for k, v in data.model_dump().items():
            f.write(f"{k}={v}\n")
    
    # Ricarica le variabili d'ambiente istantaneamente
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
    if len(history) > 15:
        print("🧹 [MEMORY] Finestra di contesto piena. Avvio compattazione...")
        from core.llm_factory import get_llm
        from langchain_core.messages import SystemMessage, HumanMessage
        
        da_compattare = history[:-4]
        da_mantenere = history[-4:]
        
        testo_da_riassumere = "\n".join([f"{m['role'].upper()}: {m['content']}" for m in da_compattare])
        
        prompt_path = os.path.join("prompts", "compaction.md")
        try:
            with open(prompt_path, "r", encoding="utf-8") as f:
                prompt_compattazione = f.read()
        except Exception:
            prompt_compattazione = "Riassumi questa conversazione in modo conciso."
             
        try:
            llm = await get_llm(task_type="fast", temperature=0.0)
            res = await llm.ainvoke([
                SystemMessage(content=prompt_compattazione),
                HumanMessage(content=testo_da_riassumere)
            ])
            
            riassunto_storico = {
                "id": str(uuid.uuid4()), 
                "role": "system", 
                "content": f"[RIASSUNTO EVENTI PASSATI]:\n{res.content}", 
                "source": "system"
            }
            
            nuova_history = [riassunto_storico] + da_mantenere
            
            with open(GLOBAL_HISTORY_FILE, "w", encoding="utf-8") as f:
                json.dump(nuova_history, f, indent=2, ensure_ascii=False)
            print("🧹 [MEMORY] Compattazione completata. Contesto alleggerito!")
        except Exception as e:
            print(f"🧹 [MEMORY] Errore durante la compattazione: {e}")

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
    langchain_messages = [SystemMessage(content=sys_prompt)]
    
    history_data = get_global_history()
    
    for msg in history_data:
        content = msg.get("content", "")
        if msg.get("role") == "user":
            langchain_messages.append(HumanMessage(content=content))
        elif msg.get("role") == "ai":
            langchain_messages.append(AIMessage(content=content))
            
    return langchain_messages

@app.get("/api/models")
async def get_available_models(engine: str = "ollama"):
    if engine == "ollama":
        try:
            async with httpx.AsyncClient() as client:
                res = await client.get("http://localhost:11434/api/tags", timeout=2.0)
                if res.status_code == 200:
                    models = [m["name"] for m in res.json().get("models", []) if "embed" not in m["name"].lower()]
                    return {"models": models}
        except Exception:
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
        
    # IMPORTANTE: Ora usiamo await perché il Bootstrapper è asincrono
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

    # --- Salviamo il file permanentemente nella storia ---
    content_to_save = message
    if file and file.filename:
        file_path = _save_upload(file)
        estensione = os.path.splitext(file.filename)[1].lower()
        
        # Diciamo chiaramente all'Agente di usare il tool giusto in base al file!
        if estensione in [".pdf", ".txt", ".md", ".docx", ".csv"]:
            content_to_save += f"\n\n[📂 DOCUMENTO ALLEGATO: {file_path} | REGOLA CRITICA DI SISTEMA: DEVI INVOCARE IMMEDIATAMENTE IL TOOL `leggi_documento` PASSANDO QUESTO PERCORSO. È SEVERAMENTE VIETATO SCRIVERE PREAMBOLI, SPIEGAZIONI O DIRE 'LO FARÒ'. ESEGUI IL TOOL IN ASSOLUTO SILENZIO ORA.]"
        elif estensione in [".png", ".jpg", ".jpeg", ".webp"]:
            content_to_save += f"\n\n[🖼️ IMMAGINE ALLEGATA: {file_path} | Usa il tool di Visione per analizzarla.]"
        else:
            content_to_save += f"\n\n[📎 FILE ALLEGATO: {file_path}]"
        
    add_to_global_history("user", content_to_save, source="web")

    # CHIAMATA CORRETTA: Nessun argomento passato
    langchain_messages = build_langchain_messages_from_global()

    async def event_generator():
        try:
            task_type = "fast" if mode == "fast" else "reasoning"
            agent = await get_agent_executor(task_type=task_type)
            inputs = {"messages": langchain_messages}
            
            yield f"data: {json.dumps({'type': 'status', 'content': '🧠 Avvio sistema cognitivo...'})}\n\n"

            final_message_content = ""
            
            # --- NUOVO MOTORE DI STREAMING DEL RAGIONAMENTO IN TEMPO REALE ---
            # astream(stream_mode="updates") emette un evento ogni volta che un Nodo (LLM o Tool) finisce
            async for event in agent.astream(inputs, stream_mode="updates"):
                if "agent" in event:
                    # L'agente ha formulato un pensiero o deciso di usare un tool
                    msg = event["agent"]["messages"][0]
                    if hasattr(msg, "tool_calls") and msg.tool_calls:
                        for tc in msg.tool_calls:
                            tool_name = tc.get("name", "Sconosciuto")
                            # Inviamo il pensiero al frontend!
                            yield f"data: {json.dumps({'type': 'reasoning', 'content': f'🛠️ Chiamata strumento: {tool_name}'})}\n\n"
                    elif msg.content:
                        # Se non ci sono tool calls, questa è la risposta finale!
                        final_message_content = msg.content
                
                elif "tools" in event:
                    # Un tool ha appena finito di lavorare e ha restituito i dati all'Agente
                    yield f"data: {json.dumps({'type': 'reasoning', 'content': '✅ Tool completato. Analizzo i risultati...'})}\n\n"

            yield f"data: {json.dumps({'type': 'status', 'content': '✍️ Scrittura completata.'})}\n\n"
            
            # Fallback di sicurezza se la stringa è vuota
            if not final_message_content:
                final_message_content = "Operazione terminata, ma nessun dato testuale restituito."

            # Salviamo nella memoria storica
            add_to_global_history("ai", final_message_content, source="web")

            # Streamiamo la parola finale lettera per lettera (effetto digitazione)
            chunk_size = 4
            for i in range(0, len(final_message_content), chunk_size):
                testo_parziale = final_message_content[i:i+chunk_size]
                yield f"data: {json.dumps({'type': 'chunk', 'content': testo_parziale})}\n\n"
                await asyncio.sleep(0.015) 
            
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
        
        inputs = {"messages": langchain_messages}
        result = await agent.ainvoke(inputs)
        
        final_message = ""
        if result and "messages" in result:
            messages = result["messages"]
            for msg in reversed(messages):
                if msg.type == "ai" and not getattr(msg, "tool_calls", None) and msg.content:
                    final_message = msg.content
                    break
            
            if not final_message:
                for msg in reversed(messages):
                    if msg.type == "tool" and msg.content:
                        final_message = f"🤖 **Risultato Estratto dal Tool:**\n{msg.content}"
                        break
                        
        if not final_message:
            final_message = "Operazione terminata, ma nessun dato estratto."
            
        add_to_global_history("ai", final_message, source="telegram")
            
        return {"response": final_message, "status": "ok"}
    except Exception as e:
        return {"response": f"Errore interno: {str(e)}", "status": "error"}

if __name__ == "__main__":
    import uvicorn
    
    # Tauri sceglie una porta libera e ce la passa qui come argomento
    port = 8000
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except:
            pass
            
    # Passo diretto dell'oggetto 'app' per supportare la compilazione con PyInstaller
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")
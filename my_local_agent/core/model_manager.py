# core/model_manager.py
import subprocess
import os
import signal
import time
import socket
import sys
import platform
import httpx
import shutil
import psutil

current_process = None
ACTIVE_SERVER_ENGINE = None
ACTIVE_SERVER_MODEL = None
OLLAMA_URL_MAC = "https://ollama.com/download/Ollama-darwin.zip"

def get_active_server_info():
    return ACTIVE_SERVER_ENGINE, ACTIVE_SERVER_MODEL

def is_ollama_running() -> bool:
    """Verifica se Ollama è già attivo nel sistema (evita conflitti di porta)."""
    try:
        with socket.create_connection(("127.0.0.1", 11434), timeout=0.5):
            return True
    except OSError:
        pass
    
    for proc in psutil.process_iter(['name']):
        try:
            if proc.info['name'] and 'ollama' in proc.info['name'].lower():
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
            
    return False

async def installa_ollama_automaticamente():
    """Scarica e configura Ollama localmente nei Documenti se non è nel sistema."""
    sistema = platform.system().lower()
    app_data_dir = os.path.expanduser("~/Documents/AI_OS_Data")
    bin_dir = os.path.join(app_data_dir, "bin")
    os.makedirs(bin_dir, exist_ok=True)
    
    target_path = os.path.join(bin_dir, "ollama")
    
    if os.path.exists(target_path):
        return target_path

    print("📦 [BOOTSTRAP] Ollama non trovato. Avvio download automatico in background...")
    
    if sistema == "darwin":
        async with httpx.AsyncClient(timeout=300.0) as client:
            response = await client.get(OLLAMA_URL_MAC, follow_redirects=True)
            zip_path = os.path.join(app_data_dir, "ollama.zip")
            with open(zip_path, "wb") as f:
                f.write(response.content)
            
            print("📦 [BOOTSTRAP] Download completato. Estrazione in corso...")
            subprocess.run(["unzip", "-o", "-q", zip_path, "-d", bin_dir], check=True)
            
            inner_bin = os.path.join(bin_dir, "Ollama.app/Contents/Resources/ollama")
            if os.path.exists(inner_bin):
                shutil.copy(inner_bin, target_path)
                os.chmod(target_path, 0o755)
            
            os.remove(zip_path)
            shutil.rmtree(os.path.join(bin_dir, "Ollama.app"), ignore_errors=True)
            
        return target_path
    
    return None

def wait_for_port(port: int, timeout: int = 120):
    """Attende che il server AI apra la porta."""
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=1):
                return True
        except (ConnectionRefusedError, TimeoutError, OSError):
            time.sleep(1)
    return False

def kill_process_on_port(port: int):
    try:
        for proc in psutil.process_iter(['pid', 'name']):
            try:
                for conns in proc.connections(kind='inet'):
                    if conns.laddr.port == port:
                        print(f"🔪 [SYSTEM] Trovato processo orfano sulla porta {port} (PID: {proc.pid}). Terminazione forzata...")
                        proc.kill()
                        proc.wait(timeout=3)
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
    except Exception:
        pass

async def start_engine(engine_type: str, model_name: str, port: int = 8080):
    global current_process, ACTIVE_SERVER_ENGINE, ACTIVE_SERVER_MODEL
    
    if engine_type == "ollama" and is_ollama_running():
        print("✅ [MOTORE] Ollama è già in esecuzione in background. Mi collego...")
        return True, "Ollama è già attivo nel sistema."

    stop_engine()
    kill_process_on_port(port)

    # --- PARAMETRI TURBOQUANT ---
    # Recuperiamo il numero di bit dalla variabile d'ambiente o usiamo 3 come default
    tq_bits = os.getenv("TURBOQUANT_BITS", "3")
    env = os.environ.copy()

    try:
        if engine_type == "mlx":
            if sys.platform != "darwin" or platform.machine() != "arm64":
                return False, "Il motore MLX e TurboQuant sono supportati esclusivamente su Mac Apple Silicon (M1/M2/M3)."

            # Comando standard raccomandato dai log.
            # FIX: Disabilitiamo i blocchi <think> per evitare che Langchain e i tool call vengano inghiottiti dai modelli di reasoning (come QwQ o Qwen-R1)
            # Utilizziamo mlx_server_patch.py per applicare runtime fix di compatibilità a modelli Gemma 4
            patch_script = os.path.join(os.path.dirname(os.path.dirname(__file__)), "mlx_server_patch.py")
            if os.path.exists(patch_script):
                comando = [sys.executable, patch_script, "--model", model_name, "--port", str(port), "--chat-template-args", '{"enable_thinking":false}']
            else:
                comando = [sys.executable, "-m", "mlx_lm", "server", "--model", model_name, "--port", str(port), "--chat-template-args", '{"enable_thinking":false}']
            
            # --- SPECULATIVE DECODING IBRIDO (UAG / dflash) ---
            import config
            draft_model = getattr(config, "MLX_DRAFT_MODEL_NAME", None)
            if draft_model:
                print(f"⚡ [UAG ATTIVO] Decodifica Speculativa Cross-Model in uso con il drafter: {draft_model}")
                comando.extend(["--draft-model", draft_model])
            
            try:
                import mlx_turboquant
                print(f"🚀 [BETA] TurboQuant ATTIVO: Ottimizzazione cache {tq_bits}-bit KV.")
                # Passiamo i parametri tramite variabili d'ambiente, che le build beta leggono all'avvio
                env["MLX_KV_CACHE_TYPE"] = "turboquant"
                env["MLX_KV_CACHE_BITS"] = str(tq_bits)
            except ImportError:
                print("ℹ️ [MLX] Avvio server standard (TurboQuant non trovato).")
            
            print(f"⏳ Avvio server MLX per {model_name}...")
            check_port = port
            
        elif engine_type == "ollama":
            ollama_path = shutil.which("ollama")
            
            if not ollama_path:
                for p in ["/opt/homebrew/bin/ollama", "/usr/local/bin/ollama"]:
                    if os.path.exists(p):
                        ollama_path = p
                        break
                        
            if not ollama_path:
                local_path = os.path.expanduser("~/Documents/AI_OS_Data/bin/ollama")
                if os.path.exists(local_path):
                    ollama_path = local_path
            
            if not ollama_path:
                ollama_path = await installa_ollama_automaticamente()

            if not ollama_path:
                return False, "Impossibile trovare o installare Ollama automaticamente."

            comando = [ollama_path, "serve"]
            
            # Iniezione variabili d'ambiente per build sperimentali di Ollama (PR #15125)
            if tq_bits:
                print(f"🚀 [BETA] Iniezione variabili d'ambiente TurboQuant per il demone Ollama...")
                env["OLLAMA_KV_CACHE_TYPE"] = "turboquant"
                env["OLLAMA_KV_CACHE_BITS"] = tq_bits

            print(f"⏳ Avvio demone Ollama (eseguibile: {ollama_path})...")
            check_port = 11434
        elif engine_type == "mtplx":
            if sys.platform != "darwin" or platform.machine() != "arm64":
                return False, "Il motore MTPLX è supportato esclusivamente su Mac Apple Silicon (M1/M2/M3/M4/M5)."

            # Trova l'eseguibile mtplx nella stessa directory dell'eseguibile python attuale
            mtplx_bin = os.path.join(os.path.dirname(sys.executable), "mtplx")
            if not os.path.exists(mtplx_bin):
                mtplx_bin = shutil.which("mtplx") or "mtplx"

            # Costruiamo il comando per avviare il server OpenAI compatibile di MTPLX
            comando = [
                mtplx_bin,
                "quickstart",
                "--model", model_name,
                "--port", str(port),
                "--no-stats-footer",
                "--download",
                "--yes"
            ]

            print(f"⏳ Avvio server MTPLX per {model_name}...")
            check_port = port
        else:
            return False, "Motore non supportato"


        # Avviamo il processo ereditando nativamente i log nel terminale
        current_process = subprocess.Popen(
            comando, 
            stdout=None,
            stderr=None, 
            env=env 
        )

        # Aumentiamo il timeout da 120 a 600 secondi (10 minuti) per permettere il download
        is_ready = wait_for_port(check_port, timeout=600)

        if is_ready:
            ACTIVE_SERVER_ENGINE = engine_type
            ACTIVE_SERVER_MODEL = model_name
            print(f"✅ Motore {engine_type} online e pronto sulla porta {check_port}!")
            return True, "Motore avviato con successo."
        else:
            stop_engine()
            return False, "Timeout: il server non si è avviato in tempo."

    except Exception as e:
        return False, f"Errore critico nell'avvio del motore: {e}"

def stop_engine():
    global current_process, ACTIVE_SERVER_ENGINE, ACTIVE_SERVER_MODEL
    if current_process:
        try:
            print("🛑 Spegnimento del motore AI per liberare la memoria...")
            current_process.terminate()
            current_process.wait(timeout=5)
        except Exception as e:
            print(f"⚠️ Chiusura forzata necessaria: {e}")
            current_process.kill()
        current_process = None
        ACTIVE_SERVER_ENGINE = None
        ACTIVE_SERVER_MODEL = None
        return True, "Motore spento con successo."
    return False, "Nessun motore da spegnere."

vision_process = None

async def start_vision_engine_if_needed(port: int = 8081):
    global vision_process
    import config
    import platform
    import sys
    
    # Se non siamo su Mac, non serve mlx_vlm, usiamo Ollama nativo.
    if sys.platform != "darwin" or platform.machine() != "arm64":
        return True

    # Verifica se è già in ascolto
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.5):
            return True
    except OSError:
        pass

    print(f"👁️ [MOTORE VISIVO] Avvio mlx_vlm in background sulla porta {port}...")
    model_name = getattr(config, "MLX_VISION_MODEL_NAME", "mlx-community/Qwen2-VL-2B-Instruct-4bit")
    
    comando = [
        sys.executable,
        "-m",
        "mlx_vlm.server",
        "--model",
        model_name,
        "--port",
        str(port),
    ]

    vision_process = subprocess.Popen(
        comando,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    is_ready = wait_for_port(port, timeout=600)
    if is_ready:
        print(f"✅ [MOTORE VISIVO] mlx_vlm pronto sulla porta {port}.")
        return True
    else:
        print("❌ [MOTORE VISIVO] Timeout durante l'avvio di mlx_vlm.")
        return False
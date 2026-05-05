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
OLLAMA_URL_MAC = "https://ollama.com/download/Ollama-darwin.zip"

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

async def start_engine(engine_type: str, model_name: str, port: int = 8080):
    global current_process
    
    if engine_type == "ollama" and is_ollama_running():
        print("✅ [MOTORE] Ollama è già in esecuzione in background. Mi collego...")
        return True, "Ollama è già attivo nel sistema."

    stop_engine()

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
            comando = [sys.executable, "-m", "mlx_lm", "server", "--model", model_name, "--port", str(port), "--chat-template-args", '{"enable_thinking":false}']
            
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
            print(f"✅ Motore {engine_type} online e pronto sulla porta {check_port}!")
            return True, "Motore avviato con successo."
        else:
            stop_engine()
            return False, "Timeout: il server non si è avviato in tempo."

    except Exception as e:
        return False, f"Errore critico nell'avvio del motore: {e}"

def stop_engine():
    global current_process
    if current_process:
        try:
            print("🛑 Spegnimento del motore AI per liberare la memoria...")
            current_process.terminate()
            current_process.wait(timeout=5)
        except Exception as e:
            print(f"⚠️ Chiusura forzata necessaria: {e}")
            current_process.kill()
        current_process = None
        return True, "Motore spento con successo."
    return False, "Nessun motore da spegnere."
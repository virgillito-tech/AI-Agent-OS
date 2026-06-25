# core/llm_factory.py
from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI
import config
import os
import socket
import asyncio
from core.model_manager import start_engine, get_active_server_info

_llm_cache = {}

import sys
import platform

HAS_MLX_TQ = False
if sys.platform == "darwin" and platform.machine() == "arm64":
    try:
        import mlx_turboquant
        HAS_MLX_TQ = True
    except ImportError:
        pass

_LAST_MLX_MODEL = None

async def get_llm(task_type: str = "reasoning", temperature: float = 0.0) -> ChatOllama | ChatOpenAI:
    global _LAST_MLX_MODEL
    engine = getattr(config, "ACTIVE_ENGINE", "ollama")
    max_t = int(getattr(config, "MAX_TOKENS", 4096))
    tq_bits = int(os.getenv("TURBOQUANT_BITS", 3))
    if task_type == "fast":
        engine = "mtplx"
        model_name = getattr(config, "MLX_FAST_MODEL_NAME", "Youssofal/Qwen3.5-4B-MTPLX-Optimized-Speed")
    else:
        engine = "mlx"
        model_name = getattr(config, "MLX_TEXT_MODEL_NAME", "mlx-community/gemma-4-12B-it-qat-4bit")
        
    if engine in ["mlx", "mtplx"]:
        
        server_active = False
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(('127.0.0.1', 8080)) == 0:
                server_active = True
                
        active_engine, active_model = get_active_server_info()
        
        if server_active and active_engine == engine and active_model == model_name:
            target_model = model_name
        else:
            print(f"⚠️ [LLM FACTORY] Switch automatico richiesto. Avvio {engine.upper()} con {model_name}...")
            await start_engine(engine, model_name)
            target_model = model_name

        key = (engine, target_model, temperature)
        if key not in _llm_cache:
            if HAS_MLX_TQ and engine == "mlx":
                print(f"🚀 [BETA] TurboQuant ATTIVO: Ottimizzazione {tq_bits}-bit KV.")
            _llm_cache[key] = ChatOpenAI(
                model=target_model,
                base_url=f"{getattr(config, 'MLX_BASE_URL', 'http://localhost:8080')}/v1",
                api_key="not-needed",
                temperature=temperature,
                max_tokens=max_t,
                timeout=1200.0,
                max_retries=1
            )
    else:  
        model_name = getattr(config, "FAST_MODEL_NAME", "qwen2.5:3b") if task_type == "fast" else getattr(config, "TEXT_MODEL_NAME", "qwen2.5:14b")
        key = (engine, model_name, temperature)
        if key not in _llm_cache:
            _llm_cache[key] = ChatOllama(model=model_name, temperature=temperature)

    return _llm_cache[key]

def get_vision_llm():
    """Ritorna l'LLM visivo appropriato: mlx_vlm per Apple Silicon, Ollama altrimenti."""
    if sys.platform == "darwin" and platform.machine() == "arm64":
        return ChatOpenAI(
            model=getattr(config, "MLX_VISION_MODEL_NAME", "mlx-community/Qwen2-VL-2B-Instruct-4bit"),
            base_url="http://localhost:8081/v1",
            api_key="not-needed",
            temperature=0,
            max_tokens=4096,
            timeout=1200.0,
            max_retries=1
        )
    else:
        return ChatOllama(model=getattr(config, "VISION_MODEL_NAME", "llama3.2-vision"), temperature=0)
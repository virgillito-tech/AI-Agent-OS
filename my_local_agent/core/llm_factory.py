# core/llm_factory.py
from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI
import config
import os
import socket
import asyncio
from core.model_manager import start_engine

_llm_cache = {}

try:
    import mlx_turboquant
    HAS_MLX_TQ = True
except ImportError:
    HAS_MLX_TQ = False

async def get_llm(task_type: str = "reasoning", temperature: float = 0.0) -> ChatOllama | ChatOpenAI:
    engine = getattr(config, "ACTIVE_ENGINE", "ollama")
    max_t = int(getattr(config, "MAX_TOKENS", 4096))
    tq_bits = int(os.getenv("TURBOQUANT_BITS", 3))
    
    if engine == "mlx":
        model_name = getattr(config, "MLX_FAST_MODEL_NAME", "mlx-community/Qwen2.5-3B-Instruct-4bit") if task_type == "fast" else getattr(config, "MLX_TEXT_MODEL_NAME", "mlx-community/Qwen2.5-14B-Instruct-4bit")
        
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(('127.0.0.1', 8080)) != 0:
                print(f"⚠️ [LLM FACTORY] Server MLX non rilevato. Avvio automatico...")
                await start_engine("mlx", model_name)

        key = (engine, model_name, temperature)
        if key not in _llm_cache:
            if HAS_MLX_TQ:
                print(f"🚀 [BETA] TurboQuant ATTIVO: Ottimizzazione {tq_bits}-bit KV.")
            _llm_cache[key] = ChatOpenAI(
                model=model_name,
                base_url=f"{getattr(config, 'MLX_BASE_URL', 'http://localhost:8080')}/v1",
                api_key="not-needed",
                temperature=temperature,
                max_tokens=max_t,
                timeout=300.0
            )
    else:  
        model_name = getattr(config, "FAST_MODEL_NAME", "qwen2.5:3b") if task_type == "fast" else getattr(config, "TEXT_MODEL_NAME", "qwen2.5:14b")
        key = (engine, model_name, temperature)
        if key not in _llm_cache:
            _llm_cache[key] = ChatOllama(model=model_name, temperature=temperature)

    return _llm_cache[key]
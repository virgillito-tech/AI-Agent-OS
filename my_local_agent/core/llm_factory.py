# core/llm_factory.py
from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI
import config

_llm_cache = {}

def get_llm(task_type: str = "reasoning", temperature: float = 0.0) -> ChatOllama | ChatOpenAI:
    engine = getattr(config, "ACTIVE_ENGINE", "ollama")
    max_t = int(getattr(config, "MAX_TOKENS", 2048))
    
    if engine == "mlx":
        # Gestione differenziata per MLX
        if task_type == "fast":
            model_name = getattr(config, "MLX_FAST_MODEL_NAME", "mlx-community/Qwen2.5-3B-Instruct-4bit")
        else:
            model_name = getattr(config, "MLX_TEXT_MODEL_NAME", "mlx-community/Qwen3.5-9B-MLX-4bit")
            
        key = (engine, model_name, temperature)
        if key not in _llm_cache:
            print(f"📦 [LLM FACTORY] Inizializzazione nuovo modello MLX: {model_name} | Task: {task_type} | Max Tokens: {max_t}")
            _llm_cache[key] = ChatOpenAI(
                model=model_name,
                base_url=getattr(config, "MLX_BASE_URL", "http://localhost:8080"),
                api_key="not-needed",
                temperature=temperature,
                max_tokens=max_t,
                timeout=120.0
            )
        else:
            print(f"📦 [LLM FACTORY] Modello MLX {model_name} recuperato dalla CACHE.")
            
    else:  
        # Gestione differenziata per OLLAMA
        if task_type == "fast":
            model_name = getattr(config, "FAST_MODEL_NAME", "qwen2.5:3b")
        else:
            model_name = getattr(config, "TEXT_MODEL_NAME", "qwen3.5:9b") 
            
        key = (engine, model_name, temperature)
        if key not in _llm_cache:
            ctx_size = 4096 if task_type == "reasoning" else 2048
            print(f"📦 [LLM FACTORY] Inizializzazione nuovo modello OLLAMA: {model_name} | Task: {task_type} | RAM (Ctx): {ctx_size}")
            _llm_cache[key] = ChatOllama(
                model=model_name,
                base_url=getattr(config, "BASE_URL_TEXT", "http://localhost:11434"),
                temperature=temperature,
                num_predict=max_t,
                num_ctx=ctx_size,
                timeout=120.0
            )
        else:
            print(f"📦 [LLM FACTORY] Modello OLLAMA {model_name} recuperato dalla CACHE.")

    return _llm_cache[key]
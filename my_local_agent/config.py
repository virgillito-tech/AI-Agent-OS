#config.py 
import os

# Motore attivo: 'ollama' o 'mlx'
ACTIVE_ENGINE = os.getenv("ACTIVE_ENGINE", "ollama")


# Modello veloce per i task in background (Guardiano - Ollama)
FAST_MODEL_NAME = os.getenv("FAST_MODEL_NAME", "qwen2.5:14b")
# Modello veloce per i task in background (Guardiano - MLX)
#MLX_FAST_MODEL_NAME = os.getenv("MLX_FAST_MODEL_NAME", "mlx-community/Qwen2.5-3B-Instruct-4bit")
MLX_FAST_MODEL_NAME = os.getenv("MLX_FAST_MODEL_NAME", "mlx-community/Qwen2.5-14B-Instruct-4bit")

# Modello di testo (Ollama)
TEXT_MODEL_NAME = os.getenv("TEXT_MODEL_NAME", "qwen2.5:14b")
BASE_URL_TEXT = os.getenv("BASE_URL_TEXT", "http://localhost:11434")

# Modello di visione (Ollama)
VISION_MODEL_NAME = os.getenv("VISION_MODEL_NAME", "llama3.2-vision")
BASE_URL_VISION = os.getenv("BASE_URL_VISION", "http://localhost:11434")

# Modello MLX (solo Mac)
#MLX_TEXT_MODEL_NAME = os.getenv("MLX_TEXT_MODEL_NAME", "mlx-community/Qwen3.5-9B-MLX-4bit")
MLX_TEXT_MODEL_NAME = os.getenv("MLX_TEXT_MODEL_NAME", "mlx-community/Qwen2.5-14B-Instruct-4bit")
MLX_BASE_URL = os.getenv("MLX_BASE_URL", "http://localhost:8080")
#MLX_VISION_MODEL_NAME = os.getenv("MLX_VISION_MODEL_NAME", "mlx-community/Qwen3.5-9B-MLX-4bit")
MLX_VISION_MODEL_NAME = os.getenv("MLX_VISION_MODEL_NAME", "mlx-community/Qwen2.5-14B-Instruct-4bit")

# API di generazione immagini
IMAGE_GEN_API_URL = os.getenv("IMAGE_GEN_API_URL", "")
IMAGE_MODEL_NAME = os.getenv("IMAGE_MODEL_NAME", "")

# Limite di token
MAX_TOKENS = int(os.getenv("MAX_TOKENS", "8096"))

# Permessi di scrittura del File System
ALLOW_GLOBAL_WRITE = False

# API Telegram
TG_API_ID="YOUR_API_ID"
TG_API_HASH="YOUR_API_HASH"

# config.py 
import os

# --- MOTORE ATTIVO ---
# Forza l'uso di MLX per sfruttare TurboQuant
ACTIVE_ENGINE = "mlx"

# --- MODELLI MLX (Ottimizzati TurboQuant) ---
# Unifichiamo i modelli per evitare che il server crashi cercando di switchare modello sulla stessa porta
MLX_MODEL_14B = "mlx-community/Qwen2.5-14B-Instruct-4bit"

MLX_FAST_MODEL_NAME = os.getenv("MLX_FAST_MODEL_NAME", MLX_MODEL_14B)
MLX_TEXT_MODEL_NAME = os.getenv("MLX_TEXT_MODEL_NAME", MLX_MODEL_14B)
MLX_VISION_MODEL_NAME = os.getenv("MLX_VISION_MODEL_NAME", MLX_MODEL_14B)

MLX_BASE_URL = os.getenv("MLX_BASE_URL", "http://localhost:8080")

# --- MODELLI OLLAMA (Fallback) ---
TEXT_MODEL_NAME = os.getenv("TEXT_MODEL_NAME", "qwen2.5:14b")
FAST_MODEL_NAME = os.getenv("FAST_MODEL_NAME", "qwen2.5:14b")
BASE_URL_TEXT = os.getenv("BASE_URL_TEXT", "http://localhost:11434")

VISION_MODEL_NAME = os.getenv("VISION_MODEL_NAME", "llama3.2-vision")
BASE_URL_VISION = os.getenv("BASE_URL_VISION", "http://localhost:11434")

# --- PARAMETRI DI GENERAZIONE ---
# Aumentiamo il limite per permettere analisi lunghe di email e chat
MAX_TOKENS = int(os.getenv("MAX_TOKENS", "8096"))

# --- API ESTERNE E SICUREZZA ---
IMAGE_GEN_API_URL = os.getenv("IMAGE_GEN_API_URL", "")
IMAGE_MODEL_NAME = os.getenv("IMAGE_MODEL_NAME", "")
ALLOW_GLOBAL_WRITE = False

# API Telegram (Assicurati di impostarli nel file .env o qui)
TG_API_ID = os.getenv("TG_API_ID", "YOUR_API_ID")
TG_API_HASH = os.getenv("TG_API_HASH", "YOUR_API_HASH")
import asyncio

# Lock globale condiviso per prevenire la saturazione della VRAM (OOM)
ai_lock = asyncio.Lock()

# Personal AI OS Agent 🛸

Un Assistente Personale e "Sistema Operativo" AI 100% locale, progettato con un'architettura **ReAct** (Reasoning and Acting) e **LangGraph**. A differenza dei classici chatbot, questo agente interagisce fisicamente con l'ambiente desktop, il file system e il web, operando secondo il Principio del Minimo Privilegio (PoLP).

## 🌟 Caratteristiche Principali

- **Architettura Tool-Calling Rigorosa:** L'agente utilizza LLM locali (es. Llama 3.1, Qwen 2.5) per ragionare e invocare dinamicamente funzioni Python.
- **Supporto Hardware-Agnostic:** Motore flessibile che supporta backend **Ollama** o framework ottimizzati per Apple Silicon (**MLX**).
- **Sicurezza e Sandbox:** Il sistema opera nativamente in una directory Sandbox isolata, con la possibilità di richiedere permessi globali (Jailbreak Controllato).
- **Memoria RAG & Contesto Globale:** Utilizza **Qdrant** come database vettoriale locale per la memoria a lungo termine e sincronizza lo storico in tempo reale tra la Web UI e un client Telegram.
- **Integrazioni Web e Desktop:** Automazione web invisibile tramite Playwright e Telethon per lettura chat, invio email via SMTP e controllo file.
- **Generazione Immagini Locale (Edge AI):** Implementa pipeline **Diffusers (SDXL)** allocando automaticamente le risorse su NVIDIA CUDA o Apple MPS per rendering in pochi secondi.

## 🛠️ Stack Tecnologico
- **Backend:** FastAPI, LangChain, LangGraph, Qdrant, Diffusers
- **Frontend:** Next.js (React), TailwindCSS, Server-Sent Events (SSE)
- **Local AI Engines:** Ollama, Apple MLX, Whisper (trascrizione vocale)

## 🚀 Installazione e Avvio (Sviluppatori)

1. **Clona la repository e installa le dipendenze Python:**
   ```bash
   git clone [https://github.com/TUO_USERNAME/ai-os-agent.git](https://github.com/TUO_USERNAME/ai-os-agent.git)
   cd ai-os-agent
   python -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

2. **Avvia il Backend FastAPI:**
```bash
uvicorn main:app --reload
```

3. **Avvia il Frontend Next.js (In un altro terminale):**
```bash
npm run dev
```

**Configurazione (.env)**
```bash
TELEGRAM_TOKEN=tuo_token_bot
TG_API_ID=tuo_api_id
TG_API_HASH=tuo_api_hash
EMAIL_USER=tuo_indirizzo_email
EMAIL_PASSWORD=tua_app_password
```
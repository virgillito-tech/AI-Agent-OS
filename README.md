# 🛸 AI Agent OS (Versione 1.0)

Un Assistente Personale e vero e proprio "Sistema Operativo" AI **100% locale**. 
A differenza dei classici chatbot, questo agente interagisce fisicamente con il tuo ambiente desktop, legge i tuoi file, naviga sul web e vigila in background, il tutto mantenendo i tuoi dati strettamente privati sul tuo hardware.

Questa Versione 1.0 segna il passaggio a un'applicazione desktop nativa e indipendente (Tauri + Python Sidecar), concepita per un'esperienza "Zero-Config": scarichi l'app, fai doppio clic e l'intelligenza artificiale prende vita senza dover toccare il terminale.

---

## Novità della Versione 1.0

* **Zero-Config Bootstrap:** Se non hai un motore LLM, l'app scaricherà e configurerà automaticamente Ollama in un ambiente isolato al primo avvio.
* **Demone "Guardiano" Proattivo:** Un processo in background (Daemon) monitora silenziosamente Gmail, iCloud e Telegram. Se rileva un'urgenza, ti invia autonomamente una notifica push sul telefono.
* **Architettura Stand-Alone:** Nessun terminale richiesto. Il frontend (React) e il backend (FastAPI/Python) sono incapsulati in un singolo eseguibile (`.dmg` / `.exe`) gestito da Tauri.
* **Telemetria Hardware in Tempo Reale:** HUD integrato per il monitoraggio live del carico su CPU, RAM e GPU (Apple Silicon & NVIDIA).

---

## Caratteristiche Core

* **Architettura ReAct (Reasoning and Acting):** L'agente ragiona e decide quali funzioni Python (Tool) invocare in base al contesto.
* **Hardware-Agnostic:** Supporto nativo e ottimizzato per **Ollama** e **Apple MLX** (sfruttando le GPU dei Mac M1/M2/M3).
* **Sicurezza PoLP (Principio del Minimo Privilegio):** Esecuzione confinata in una Sandbox nativa. L'agente non può scrivere fuori dalla sua cartella a meno che tu non attivi il "Jailbreak Controllato".
* **Memoria RAG & Contesto Globale:** Utilizzo di un database vettoriale locale per la memoria a lungo termine, con auto-compattazione semantica quando il contesto si riempie.
* **Integrazioni Web e Desktop:** Automazione invisibile tramite Playwright (es. WhatsApp Web) e lettura nativa delle email via IMAP/SMTP.
* **Ascolto Vocale (Edge AI):** Modello Whisper integrato per la trascrizione audio ultra-rapida sul dispositivo.

---

## Stack Tecnologico

* **Frontend:** Tauri v2, Next.js (React), TailwindCSS.
* **Backend:** FastAPI, Python (PyInstaller Sidecar).
* **Logica AI:** LangChain, LangGraph.
* **Motori Locali:** Ollama, MLX, Faster-Whisper.

---

## Installazione

### Per Utenti (Plug & Play)
Non è richiesta alcuna conoscenza tecnica.
1. Vai nella sezione **Releases** di questo repository.
2. Scarica il file di installazione per il tuo sistema (`.dmg` per macOS, `.exe` per Windows).
3. Apri l'applicazione. L'ambiente si configurerà da solo e scaricherà i modelli necessari.

### Per Sviluppatori (Build da Sorgente)

Per compilare l'app da zero e modificare il codice sorgente:

**1. Clona e prepara il Backend (Python)**
Crea l'ambiente virtuale e installa le dipendenze:
`git clone https://github.com/TUO_USERNAME/ai-agent-os.git`
`cd ai-agent-os/backend`
`pip install -r requirements.txt`

**2. Compila il Sidecar (PyInstaller)**
Congela il motore Python in un eseguibile:
`pyinstaller --name "ai-os-backend" --onefile --add-data "prompts:prompts" main.py`

**3. Sposta l'eseguibile in Tauri**
Sposta il file generato dalla cartella `dist/` alla cartella `src-tauri/bin/` del frontend.
*Nota: Rinomina il file aggiungendo la tua architettura di destinazione (es. `ai-os-backend-aarch64-apple-darwin` per Mac Silicon).*

**4. Compila il Frontend (Tauri)**
`cd ../frontend`
`npm install`
`npm run tauri build`

---

## Configurazione (.env)

Per abilitare le funzionalità di comunicazione (Mail, Telegram), l'app genererà una cartella sicura in `~/Documents/AI_OS_Data/`. Inserisci lì dentro il tuo file `.env` con queste chiavi:

`TELEGRAM_TOKEN=tuo_token_bot`
`TG_API_ID=tuo_api_id`
`TG_API_HASH=tuo_api_hash`
`EMAIL_USER=tuo_indirizzo_email`
`EMAIL_PASSWORD=tua_app_password`

# --- API Generazione Immagini (Opzionale) ---
`IMAGE_GEN_API_URL=http://localhost:8000/generate`
`IMAGE_MODEL_NAME=flux`
`SANDBOX_DIR=sandbox`

`ICLOUD_EMAIL==********`
`ICLOUD_APP_PASSWORD=********`

# --- CONFIGURAZIONE OLLAMA (Motore Standard) ---
`ACTIVE_ENGINE=ollama`
`TEXT_MODEL_NAME=****`
`FAST_MODEL_NAME=****`
`BASE_URL_TEXT=http://localhost:11434`
`VISION_MODEL_NAME=****`
`BASE_URL_VISION=http://localhost:11434`
`MAX_TOKENS=4096`

# --- CONFIGURAZIONE MLX (Solo Mac con M-Series) ---
`MLX_TEXT_MODEL_NAME=mlx-community/*******`
`MLX_BASE_URL=http://localhost:8080`
`MLX_VISION_MODEL_NAME=mlx-community/*****`
`MLX_FAST_MODEL_NAME=mlx-community/*******`

---
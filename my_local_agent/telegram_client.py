# telegram_client.py
import httpx
import os
import sys
import json
import tempfile
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from dotenv import load_dotenv  
from telegram import Update

# Carico il file .env 
load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
if not TELEGRAM_TOKEN:
    print("❌ ERRORE: la variabile d'ambiente TELEGRAM_TOKEN non è impostata. Avvio annullato.")
    sys.exit(1)

API_SYNC_URL = "http://127.0.0.1:8000/api/chat/sync"

async def _call_agent(prompt: str, mode: str = "agent"):
    """Chiama il nuovo endpoint sync del backend che gestisce la storia da solo."""
    async with httpx.AsyncClient(timeout=120.0) as client:
        try:
            data = {
                "message": prompt,
                "mode": mode,
                "engine": "ollama" # o "mlx" se usi il mac
            }
            # Ora usiamo l'endpoint sync pulito
            response = await client.post("http://localhost:8000/api/chat/sync", data=data)
            response.raise_for_status()
            return response.json().get("response", "Nessuna risposta dal server.")
        except Exception as e:
            return f"Errore di comunicazione col server AI: {e}"

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # 1. Salviamo il Chat ID per il Guardiano Proattivo
    chat_id = update.effective_chat.id
    os.makedirs("sandbox", exist_ok=True)
    with open(os.path.join("sandbox", "tg_chat_id.txt"), "w") as f:
        f.write(str(chat_id))

    # 2. Gestiamo il messaggio
    mode = context.user_data.get("mode", "agent")
    await context.bot.send_chat_action(chat_id=chat_id, action="typing")
    
    # Non passiamo più la history, ci pensa il backend!
    response = await _call_agent(update.message.text, mode=mode)
    
    # 3. Inviamo la risposta spezzandola se supera i limiti di Telegram
    chunk_size = 4000
    for i in range(0, len(response), chunk_size):
        await update.message.reply_text(response[i:i+chunk_size])


async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    
    # Salviamo l'ID anche qui, così se il primo messaggio è vocale il Guardiano sa a chi scrivere
    os.makedirs("sandbox", exist_ok=True)
    with open(os.path.join("sandbox", "tg_chat_id.txt"), "w") as f:
        f.write(str(chat_id))

    await context.bot.send_chat_action(chat_id=chat_id, action="record_voice")

    try:
        # 1. Prendi il file audio da Telegram
        voice_file = await context.bot.get_file(update.message.voice.file_id)
        
        # 2. Scaricalo in un file temporaneo
        with tempfile.NamedTemporaryFile(delete=False, suffix=".ogg") as tmp:
            await voice_file.download_to_drive(tmp.name)
            tmp_path = tmp.name

        # 3. Invialo al nostro server locale (Whisper) per la trascrizione
        async with httpx.AsyncClient(timeout=120.0) as client:
            with open(tmp_path, "rb") as f:
                files = {"audio": ("voice.ogg", f, "audio/ogg")}
                res = await client.post("http://localhost:8000/api/transcribe", files=files)
                res.raise_for_status()
                testo_trascritto = res.json().get("text", "")

        # Pulizia del file
        os.remove(tmp_path)

        if not testo_trascritto:
            await update.message.reply_text("Scusa, l'audio era vuoto o non sono riuscito a capirlo.")
            return

        # Scriviamo in chat cosa abbiamo capito
        await update.message.reply_text(f"🎤 *Ho capito:* _{testo_trascritto}_", parse_mode="Markdown")

        # 4. Passiamo il testo trascritto all'Agente come se lo avessi digitato tu
        mode = context.user_data.get("mode", "agent")
        await context.bot.send_chat_action(chat_id=chat_id, action="typing")
        
        response = await _call_agent(testo_trascritto, mode=mode)

        # 5. Rispondiamo normalmente
        chunk_size = 4000
        for i in range(0, len(response), chunk_size):
            await update.message.reply_text(response[i:i+chunk_size])

    except Exception as e:
        await update.message.reply_text(f"Errore durante l'elaborazione dell'audio: {e}")

def _chunks(text: str, n: int = 4000):
    return [text[i:i + n] for i in range(0, len(text), n)]

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["mode"] = "agent"
    context.user_data["history"] = []
    msg = (
        "🤖 Benvenuto in AI OS!\n\n"
        "Comandi:\n"
        "⚡️ /fast - Modalità Chat veloce\n"
        "🧠 /agent - Modalità Agente\n"
        "🧹 /clear - Svuota la memoria della chat"
    )
    await update.message.reply_text(msg)

async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["history"] = []
    await update.message.reply_text("🧹 Memoria azzerata. Sono pronto per un nuovo task!")

async def set_fast_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["mode"] = "fast"
    await update.message.reply_text("⚡️ Modalità Fast attivata!")

async def set_agent_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["mode"] = "agent"
    await update.message.reply_text("🧠 Modalità Agente attivata!")

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mode = context.user_data.get("mode", "agent")
    history = context.user_data.get("history", [])
    
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    tmp = f"tg_photo_{os.urandom(4).hex()}.jpg"
    try:
        f = await update.message.photo[-1].get_file()
        await f.download_to_drive(tmp)
        caption = update.message.caption or "Analizza questa immagine"
        
        history.append({"role": "user", "content": caption})
        response = await _call_agent(caption, history, photo_path=tmp, mode=mode)
        history.append({"role": "ai", "content": response})
        context.user_data["history"] = history[-10:]
        
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)
            
    for chunk in _chunks(response):
        await update.message.reply_text(chunk)

def main():
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("clear", clear_command))
    application.add_handler(CommandHandler("fast", set_fast_mode))
    application.add_handler(CommandHandler("agent", set_agent_mode))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    application.add_handler(MessageHandler(filters.VOICE, handle_voice))
    print("Bot Telegram in ascolto...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
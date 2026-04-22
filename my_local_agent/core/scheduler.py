# core/scheduler.py
import os
import httpx
import asyncio
import json
import uuid
import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore

# 1. Configuriamo la Persistenza
os.makedirs("sandbox", exist_ok=True)
jobstores = {
    'default': SQLAlchemyJobStore(url='sqlite:///sandbox/os_tasks.sqlite')
}

# 2. Configurazione "Resilienza" (Grace time e Coalesce)
job_defaults = {
    'coalesce': True,           # Se saltano più esecuzioni, ne recupera solo una
    'max_instances': 1,         # Un solo task per volta
    'misfire_grace_time': 18000 # Recupera task saltati fino a 5 ore prima
}

scheduler = AsyncIOScheduler(
    jobstores=jobstores, 
    job_defaults=job_defaults,
    timezone="Europe/Rome"
)

def avvia_scheduler():
    if not scheduler.running:
        scheduler.start()
        print("⏱️ [SCHEDULER] Motore dei Cron Job avviato con successo.")

async def _esegui_task_programmato(messaggio: str, chat_id: str):
    """Promemoria semplice via Telegram."""
    print(f"\n⏰ [SCHEDULER] Driiin! Esecuzione task: {messaggio}")
    token = os.getenv("TELEGRAM_TOKEN")
    if token and chat_id:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        testo = f"🔔 *AI OS | Promemoria:*\n\n{messaggio}"
        try:
            async with httpx.AsyncClient() as client:
                await client.post(url, data={"chat_id": chat_id, "text": testo, "parse_mode": "Markdown"})
        except Exception as e:
            print(f"⏰ [SCHEDULER] ❌ Errore invio Telegram: {e}")

async def _esegui_agente_in_background(prompt_istruzione: str, chat_id: str):
    """Task complesso con Agente e sincronizzazione memoria."""
    print(f"\n⚙️ [AUTONOMIA] Avvio task programmato: {prompt_istruzione}")
    risultato_finale = ""
    token = os.getenv("TELEGRAM_TOKEN")
    
    try:
        await asyncio.sleep(5) # Evita collisioni VRAM col Guardiano
        
        from agents.core_agent import get_agent_executor
        from langchain_core.messages import HumanMessage
        
        data_oggi = datetime.datetime.now().strftime("%d %B %Y")
        agent = await get_agent_executor(task_type="reasoning")
        
        # Payload imperativo per evitare il loop dello scheduler
        payload_esecuzione = (
            f"[SISTEMA: ESECUZIONE IMMEDIATA | DATA: {data_oggi}]\n"
            f"Stai eseguendo un task pianificato. NON usare tool di programmazione.\n"
            f"AZIONE: {prompt_istruzione}"
        )
        
        res = await agent.ainvoke({"messages": [HumanMessage(content=payload_esecuzione)]})
        
        # Estrazione risposta
        if res and "messages" in res:
            for msg in reversed(res["messages"]):
                if msg.type == "ai" and msg.content and not getattr(msg, "tool_calls", None):
                    risultato_finale = msg.content
                    break
        
        if not risultato_finale:
            risultato_finale = "Task completato. Ho eseguito le azioni richieste in background."

        # --- 1. NOTIFICA TELEGRAM ---
        if token and chat_id:
            url = f"https://api.telegram.org/bot{token}/sendMessage"
            testo_invio = f"🤖 *AI OS | Task Autonomo Completato:*\n\n{risultato_finale}"
            if len(testo_invio) > 4000: testo_invio = testo_invio[:4000] + "..."
            
            async with httpx.AsyncClient(timeout=180.0) as client:
                resp = await client.post(url, data={"chat_id": chat_id, "text": testo_invio, "parse_mode": "Markdown"})
                if resp.status_code != 200:
                    await client.post(url, data={"chat_id": chat_id, "text": testo_invio}) # Fallback testo semplice

        # --- 2. SINCRONIZZAZIONE MEMORIA (Il pezzo mancante) ---
        try:
            history_file = "sandbox/global_chat_history.json"
            hist = []
            if os.path.exists(history_file):
                with open(history_file, "r", encoding="utf-8") as f:
                    hist = json.load(f)
            
            # Creiamo una nota che l'Agente della Chat leggerà al prossimo avvio
            # Usiamo 'ai' come role così l'agente crederà di averlo detto lui stesso
            mem_note = (
                f"[SISTEMA - NOTA BACKGROUND]: Ho completato con successo il task: '{prompt_istruzione}'. "
                f"Ho comunicato all'utente quanto segue: {risultato_finale[:200]}... "
                f"Se l'utente mi chiede i file generati, so che si trovano nella cartella sandbox/."
            )
            
            hist.append({
                "id": str(uuid.uuid4()), 
                "role": "ai", 
                "content": mem_note, 
                "source": "background_task"
            })
            
            with open(history_file, "w", encoding="utf-8") as f:
                json.dump(hist[-50:], f, indent=2, ensure_ascii=False)
            print("⚙️ [AUTONOMIA] 🧠 Memoria sincronizzata con la chat UI.")
            
        except Exception as e_mem:
            print(f"⚙️ [AUTONOMIA] ❌ Errore sincronizzazione memoria: {e_mem}")
            
    except Exception as e:
        print(f"⚙️ [AUTONOMIA] ❌ Errore critico: {e}")
        if token and chat_id:
            msg_err = f"❌ *AI OS | Task Fallito*\nErrore: `{e}`"
            async with httpx.AsyncClient() as client:
                await client.post(f"https://api.telegram.org/bot{token}/sendMessage", 
                                 data={"chat_id": chat_id, "text": msg_err, "parse_mode": "Markdown"})
# core/scheduler.py
import os
import httpx
import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore

# 1. Configuriamo la Persistenza: i task verranno salvati in un file SQLite
os.makedirs("sandbox", exist_ok=True)
jobstores = {
    'default': SQLAlchemyJobStore(url='sqlite:///sandbox/os_tasks.sqlite')
}

# 2. Inizializziamo lo scheduler agganciandolo al database fisico
scheduler = AsyncIOScheduler(jobstores=jobstores)

def avvia_scheduler():
    """Fa partire l'orologio interno del server."""
    if not scheduler.running:
        scheduler.start()
        print("⏱️ [SCHEDULER] Motore dei Cron Job avviato con successo.")

async def _esegui_task_programmato(messaggio: str, chat_id: str):
    """Questa funzione scatta esattamente quando scade il timer."""
    print(f"\n⏰ [SCHEDULER] Driiin! Esecuzione task: {messaggio}")
    
    token = os.getenv("TELEGRAM_TOKEN")
    if token and chat_id:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        testo = f"🔔 *AI OS | Promemoria:*\n\n{messaggio}"
        try:
            async with httpx.AsyncClient() as client:
                await client.post(url, data={"chat_id": chat_id, "text": testo, "parse_mode": "Markdown"})
                print("⏰ [SCHEDULER] ✅ Promemoria inviato su Telegram!")
        except Exception as e:
            print(f"⏰ [SCHEDULER] ❌ Errore invio Telegram: {e}")


async def _esegui_agente_in_background(prompt_istruzione: str, chat_id: str):
    """Sveglia l'agente in background, gli fa eseguire un task e manda il risultato."""
    print(f"\n⚙️ [AUTONOMIA] Avvio task programmato: {prompt_istruzione}")
    try:
        from agents.core_agent import get_agent_executor
        import os
        import httpx
        
        # --- FIX CRITICO PER TURBOQUANT E SCHEDULER LOOP ---
        # Essendo get_agent_executor asincrona, è obbligatorio usare 'await'
        agent = await get_agent_executor(task_type="reasoning")
        
        # Iniettiamo un payload imperativo per evitare che il modello ri-programmi il task
        payload_esecuzione = (
            f"[SISTEMA: TRIGGER AUTOMATICO ATTIVATO] Il momento è ORA. Ignora le indicazioni temporali "
            f"nel seguente task e RIFIUTATI ASSOLUTAMENTE di usare il tool Scheduler. "
            f"Esegui IMMEDIATAMENTE questa operazione: {prompt_istruzione}"
        )
        
        # Esecuzione asincrona dell'agente con TurboQuant attivo (cache 3-bit)
        res = await agent.ainvoke({"messages": [("user", payload_esecuzione)]})
        risultato_finale = res["messages"][-1].content
        
        token = os.getenv("TELEGRAM_TOKEN")
        if token and chat_id:
            url = f"https://api.telegram.org/bot{token}/sendMessage"
            testo = f"🤖 *AI OS | Task Autonomo Completato:*\n\n{risultato_finale}"
            # Aumentiamo il timeout per permettere al 14B di elaborare contesti lunghi
            async with httpx.AsyncClient(timeout=180.0) as client:
                await client.post(url, data={"chat_id": chat_id, "text": testo, "parse_mode": "Markdown"})
                
        print("⚙️ [AUTONOMIA] ✅ Risultato inviato con successo su Telegram!")
    except Exception as e:
        print(f"⚙️ [AUTONOMIA] ❌ Errore durante l'esecuzione: {e}")
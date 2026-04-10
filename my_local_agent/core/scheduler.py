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
        import json
        import uuid
        from langchain_core.messages import HumanMessage
        
        agent = await get_agent_executor(task_type="reasoning")
        
        payload_esecuzione = (
            f"[SISTEMA: TRIGGER AUTOMATICO ATTIVATO] Il momento è ORA. Ignora le indicazioni temporali "
            f"nel seguente task e RIFIUTATI ASSOLUTAMENTE di usare il tool Scheduler. "
            f"Esegui IMMEDIATAMENTE questa operazione: {prompt_istruzione}"
        )
        
        res = await agent.ainvoke({"messages": [("user", payload_esecuzione)]})
        
        # --- Estrazione intelligente del resoconto ---
        risultato_finale = ""
        tool_results_for_fallback = []
        
        if res and "messages" in res:
            for msg in reversed(res["messages"]):
                if msg.type == "ai" and not getattr(msg, "tool_calls", None) and msg.content:
                    risultato_finale = msg.content
                    break
                    
            # RETE DI SICUREZZA BACKGROUND
            if not risultato_finale:
                for msg in res["messages"]:
                    if msg.type == "tool":
                        tool_results_for_fallback.append(f"[{msg.name}]: {msg.content}")
                
                if tool_results_for_fallback:
                    from core.llm_factory import get_llm
                    testi_estratti = "\n".join(tool_results_for_fallback)
                    prompt_salvataggio = (
                        f"Hai appena completato questo task in autonomia: '{prompt_istruzione}'.\n"
                        f"I tool hanno prodotto questi dati:\n{testi_estratti}\n\n"
                        f"Scrivi un breve resoconto finale chiaro per l'utente in base a questi dati."
                    )
                    llm_fallback = await get_llm(task_type="fast", temperature=0.0)
                    fallback_res = await llm_fallback.ainvoke([HumanMessage(content=prompt_salvataggio)])
                    risultato_finale = fallback_res.content
        
        if not risultato_finale:
            risultato_finale = "Task completato in background senza generare testo aggiuntivo."
        
        token = os.getenv("TELEGRAM_TOKEN")
        if token and chat_id:
            url = f"https://api.telegram.org/bot{token}/sendMessage"
            testo = f"🤖 *AI OS | Task Autonomo Completato:*\n\n{risultato_finale}"
            
            async with httpx.AsyncClient(timeout=180.0) as client:
                await client.post(url, data={"chat_id": chat_id, "text": testo, "parse_mode": "Markdown"})
                
        print("⚙️ [AUTONOMIA] ✅ Risultato inviato con successo su Telegram!")
        
        # --- Sincronizziamo la memoria dell'Agente UI ---
        try:
            history_file = os.path.join("sandbox", "global_chat_history.json")
            if os.path.exists(history_file):
                with open(history_file, "r", encoding="utf-8") as f:
                    hist = json.load(f)
                
                memoria_task = (
                    f"[SISTEMA - NOTA BACKGROUND]: L'agente autonomo ha appena eseguito con successo "
                    f"questo task in background: '{prompt_istruzione}'.\n"
                    f"Il resoconto dettagliato è già stato inviato all'utente su Telegram. "
                    f"Se l'utente ne parla, confermagli che il task è stato completato e recapitato."
                )
                
                hist.append({"id": str(uuid.uuid4()), "role": "system", "content": memoria_task, "source": "scheduler"})
                
                with open(history_file, "w", encoding="utf-8") as f:
                    json.dump(hist[-50:], f, indent=2, ensure_ascii=False)
        except Exception as mem_e:
            print(f"⚙️ [AUTONOMIA] Errore salvataggio memoria history: {mem_e}")
            
    except Exception as e:
        print(f"⚙️ [AUTONOMIA] ❌ Errore durante l'esecuzione: {e}")
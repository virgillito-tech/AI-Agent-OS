# core/scheduler.py
import os
import httpx
import asyncio
import json
import uuid
import datetime
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
    """Questa funzione scatta esattamente quando scade il timer (Promemoria Semplice)."""
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
    """Sveglia l'agente in background, gli fa eseguire un task complesso e manda il risultato."""
    print(f"\n⚙️ [AUTONOMIA] Avvio task programmato: {prompt_istruzione}")
    
    # Inizializziamo le variabili per evitare errori nello scope dell'except
    risultato_finale = ""
    token = os.getenv("TELEGRAM_TOKEN")
    
    try:
        # 1. EVITIAMO COLLISIONI VRAM: Piccolo ritardo per non scontrarsi col Guardiano
        await asyncio.sleep(5)
        
        from agents.core_agent import get_agent_executor
        from langchain_core.messages import HumanMessage
        
        data_oggi = datetime.datetime.now().strftime("%d %B %Y")
        agent = await get_agent_executor(task_type="reasoning")
        
        # 2. DATA DINAMICA: Iniettiamo il 2026 per evitare ricerche nel passato
        # Forza l'agente a ESEGUIRE e non a PROGRAMMARE
        payload_esecuzione = (
            f"[SISTEMA: ESECUZIONE IMMEDIATA OBBLIGATORIA | DATA: {data_oggi}]\n"
            f"ATTENZIONE: Sei già all'interno di un task programmato. "
            f"NON USARE il tool 'Scheduler' o 'programma_task'. "
            f"Il tuo compito ORA è eseguire l'azione richiesta, non pianificarla.\n\n"
            f"AZIONE DA COMPIERE: {prompt_istruzione}"
        )
        
        res = await agent.ainvoke({"messages": [HumanMessage(content=payload_esecuzione)]})
        
        # --- Estrazione del resoconto ---
        if res and "messages" in res:
            for msg in reversed(res["messages"]):
                if msg.type == "ai" and msg.content and not getattr(msg, "tool_calls", None):
                    risultato_finale = msg.content
                    break
                    
            # Se il risultato è vuoto, proviamo ad assemblarlo dai tool
            if not risultato_finale or len(risultato_finale.strip()) < 5:
                tool_results = []
                for msg in res["messages"]:
                    if msg.type == "tool":
                        tool_results.append(f"[{msg.name}]: {msg.content}")
                
                if tool_results:
                    from core.llm_factory import get_llm
                    prompt_salvataggio = (
                        f"Hai completato questo task: '{prompt_istruzione}'.\n"
                        f"Dati estratti:\n" + "\n".join(tool_results) + 
                        "\n\nScrivi un breve resoconto finale chiaro per l'utente."
                    )
                    llm_fallback = await get_llm(task_type="fast", temperature=0.0)
                    fallback_res = await llm_fallback.ainvoke([HumanMessage(content=prompt_salvataggio)])
                    risultato_finale = fallback_res.content

        # Se dopo tutto è ancora vuoto, segnaliamo il sovraccarico
        if not risultato_finale:
            risultato_finale = "⚠️ Il task è stato eseguito ma l'AI non ha generato testo (possibile sovraccarico VRAM)."

        # --- INVIO SICURO A TELEGRAM ---
        if token and chat_id:
            url = f"https://api.telegram.org/bot{token}/sendMessage"
            testo_invio = f"🤖 *AI OS | Task Autonomo Completato:*\n\n{risultato_finale}"
            
            # Controllo lunghezza
            if len(testo_invio) > 4000:
                testo_invio = testo_invio[:4000] + "\n\n[...Troncato per lunghezza...]"
            
            async with httpx.AsyncClient(timeout=180.0) as client:
                # Tentativo 1: Markdown
                resp = await client.post(url, data={"chat_id": chat_id, "text": testo_invio, "parse_mode": "Markdown"})
                
                if resp.status_code != 200:
                    # Tentativo 2: Testo Semplice (Fallback)
                    print(f"⚙️ [AUTONOMIA] ⚠️ Errore Markdown, ritento in testo semplice...")
                    await client.post(url, data={"chat_id": chat_id, "text": testo_invio})
                
            print("⚙️ [AUTONOMIA] ✅ Risultato inviato con successo.")

        # --- SINCRONIZZAZIONE MEMORIA UI ---
        try:
            history_file = os.path.join("sandbox", "global_chat_history.json")
            if os.path.exists(history_file):
                with open(history_file, "r", encoding="utf-8") as f:
                    hist = json.load(f)
                mem_note = f"[SISTEMA - BACKGROUND]: Task completato: '{prompt_istruzione}'."
                hist.append({"id": str(uuid.uuid4()), "role": "system", "content": mem_note, "source": "scheduler"})
                with open(history_file, "w", encoding="utf-8") as f:
                    json.dump(hist[-50:], f, indent=2, ensure_ascii=False)
        except: pass
            
    except Exception as e:
        print(f"⚙️ [AUTONOMIA] ❌ Errore critico durante l'esecuzione: {e}")
        # Notifica il fallimento all'utente
        if token and chat_id:
            msg_fallito = f"❌ *AI OS | Task Fallito*\nL'operazione '{prompt_istruzione}' si è interrotta: `{e}`"
            async with httpx.AsyncClient() as client:
                await client.post(f"https://api.telegram.org/bot{token}/sendMessage", 
                                 data={"chat_id": chat_id, "text": msg_fallito, "parse_mode": "Markdown"})
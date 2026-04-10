# agents/core_agent.py
import datetime
import platform
import os
import asyncio
from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent
from core.llm_factory import get_llm
from langchain_core.messages import HumanMessage
from tools.icloud_tools import leggi_email_icloud, leggi_calendario_icloud
from tools.os_tools import leggi_stato_batteria, sospendi_computer, apri_applicazione, riproduci_audio_testo
from tools.converter_tools import converti_documento
from tools.drive_tools import esplora_google_drive, scarica_da_drive, carica_su_drive
from tools.browser_tools import automazione_login_sito, naviga_e_clicca
from tools.database_tools import gestisci_database_sqlite
from tools.social_tools import pubblica_post_twitter

# Import dei tool specialistici
from tools.agent_tools import (
    ottieni_data_ora_sistema, ricerca_web_affidabile, analyze_local_image, execute_python_code,
    save_memory, search_memory, programma_task_autonomo, apri_in_vscode,
    apri_sito_web_universale, invia_email_universale, genera_immagine_locale, leggi_ultime_email,
    invia_email_google, leggi_prossimi_eventi_calendario, _is_write_permitted, esplora_file_sistema,
    leggi_file_sistema, scrivi_o_copia_file, leggi_whatsapp, leggi_telegram_personale, 
    scatta_e_analizza_schermo, esegui_azione_mouse_tastiera, navigatore_web_integrato, 
    leggi_tutte_le_chat, leggi_pagina_web, crea_documento_pdf, 
    leggi_documento, leggi_task_programmati, elimina_task_programmato
)

# ---------------------------------------------------------
# 1. DEFINIZIONE DEI TOOLKIT DEGLI SPECIALISTI
# ---------------------------------------------------------
WEB_TOOLS = [ricerca_web_affidabile, apri_sito_web_universale, leggi_pagina_web]
DESKTOP_TOOLS = [esplora_file_sistema, leggi_file_sistema, scrivi_o_copia_file, execute_python_code, apri_in_vscode, crea_documento_pdf, leggi_stato_batteria, sospendi_computer, apri_applicazione, riproduci_audio_testo, leggi_documento, converti_documento, gestisci_database_sqlite]
COMMS_TOOLS = [leggi_ultime_email, invia_email_google, invia_email_universale, leggi_whatsapp, leggi_telegram_personale, leggi_prossimi_eventi_calendario, leggi_tutte_le_chat, leggi_email_icloud, leggi_calendario_icloud, esplora_google_drive, scarica_da_drive, carica_su_drive, pubblica_post_twitter]

# ---------------------------------------------------------
# 2. CACHE DEI SUB-AGENTI (SINGLETON PATTERN)
# ---------------------------------------------------------
# Dizionario globale che manterrà vivi i sub-agenti una volta creati
_agents_cache = {}

async def _get_cached_agent(agent_name: str, tools: list, task_type: str = "fast"):
    """Recupera l'agente dalla cache o lo costruisce (Lazy Initialization) se non esiste."""
    if agent_name not in _agents_cache:
        print(f"🔧 Inizializzazione lazy del Sub-Agente: {agent_name}...")
        llm = await get_llm(task_type=task_type)
        _agents_cache[agent_name] = create_react_agent(llm, tools)
    return _agents_cache[agent_name]

# ---------------------------------------------------------
# 3. CREAZIONE DEI SUB-AGENTI (Async Agent-as-a-Tool)
# ---------------------------------------------------------

@tool
async def delegato_ricerca_web(istruzioni: str) -> str:
    """DELEGA: Incarica il Sub-Agente Web di fare ricerche su internet."""
    print(f"\n   🤖 [SUB-AGENTE WEB] Inizio lavoro per: {istruzioni}")
    # Recupera l'agente dalla cache invece di crearlo da zero
    agent = await _get_cached_agent("web", WEB_TOOLS, "fast")
    res = await agent.ainvoke({"messages": [("user", istruzioni)]})
    return f"Risultato dall'Agente Web:\n{res['messages'][-1].content}"

@tool
async def delegato_sistema_file(istruzioni: str) -> str:
    """DELEGA: Incarica il Sub-Agente Desktop di esplorare cartelle, leggere file o eseguire codice."""
    print(f"\n   🤖 [SUB-AGENTE DESKTOP] Inizio lavoro per: {istruzioni}")
    agent = await _get_cached_agent("desktop", DESKTOP_TOOLS, "fast")
    res = await agent.ainvoke({"messages": [("user", istruzioni)]})
    return f"Risultato dall'Agente Desktop:\n{res['messages'][-1].content}"

@tool
async def delegato_comunicazioni(istruzioni: str) -> str:
    """DELEGA: Incarica il Sub-Agente Comunicazioni di gestire email, WhatsApp, Telegram."""
    print(f"\n   🤖 [SUB-AGENTE COMMS] Inizio lavoro per: {istruzioni}")
    agent = await _get_cached_agent("comms", COMMS_TOOLS, "fast")
    res = await agent.ainvoke({"messages": [("user", istruzioni)]})
    return f"Risultato dall'Agente Comunicazioni:\n{res['messages'][-1].content}"

@tool
async def delegato_automazione_ui(istruzioni: str) -> str:
    """DELEGA: Incarica il Sub-Agente UI di guardare lo schermo e muovere mouse/tastiera."""
    print(f"\n   🤖 [SUB-AGENTE UI] Inizio lavoro per: {istruzioni}")
    ui_tools = [scatta_e_analizza_schermo, esegui_azione_mouse_tastiera]
    agent = await _get_cached_agent("ui", ui_tools, "reasoning")
    res = await agent.ainvoke({"messages": [("user", istruzioni)]})
    return f"Risultato dall'Agente UI:\n{res['messages'][-1].content}"

# ---------------------------------------------------------
# 4. IL SUPERVISORE (Core Agent)
# ---------------------------------------------------------

def get_dynamic_system_prompt() -> str:
    now = datetime.datetime.now()
    os_name = platform.system()
    arch = platform.machine()
    ora_formattata = now.strftime("%Y-%m-%d %H:%M:%S")
    
    print(f"\n👑 [SUPERVISOR AGENT] Caricamento | OS: {os_name} | Data: {ora_formattata}")
    
    prompt_path = os.path.join("prompts", "system.md")
    try:
        with open(prompt_path, "r", encoding="utf-8") as f:
            template = f.read()
    except FileNotFoundError:
        return "You are the Supervisor AI. Delegate tasks."

    return template.format(
        os_name=os_name, arch=arch, ora_formattata=ora_formattata, year=now.year
    )

async def get_agent_executor(task_type: str = "reasoning"):
    """Inizializza il Supervisore Principale in modalità asincrona."""
    # Fondamentale: await get_llm per attivare TurboQuant se necessario
    llm = await get_llm(task_type=task_type)
    
    supervisor_tools = [
        delegato_ricerca_web,
        delegato_sistema_file,
        delegato_comunicazioni,
        genera_immagine_locale,
        analyze_local_image,
        leggi_documento,
        crea_documento_pdf,
        save_memory,
        search_memory,
        programma_task_autonomo,
        ottieni_data_ora_sistema,
        delegato_automazione_ui,
        navigatore_web_integrato,
        leggi_pagina_web,
        leggi_task_programmati,
        elimina_task_programmato,
        converti_documento,
        esplora_google_drive, 
        scarica_da_drive, 
        carica_su_drive,
        automazione_login_sito,
        naviga_e_clicca,
        gestisci_database_sqlite,
        pubblica_post_twitter
    ]
    
    # Restituiamo l'agente pronto per lo streaming asincrono in main.py
    return create_react_agent(llm, supervisor_tools)
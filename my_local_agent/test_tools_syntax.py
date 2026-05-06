import sys

try:
    from tools.agent_tools import (
        gestisci_calendario_universale, gestore_multimediale, parla_con_utente,
        trascrivi_e_riassumi_audio, gestisci_note_obsidian, esegui_comando_terminale_sandbox,
        gestisci_applicazioni_universale, pubblica_su_social
    )
    print("Agent tools compiled successfully.")
except Exception as e:
    print(f"Error compiling agent tools: {e}")
    sys.exit(1)

try:
    from agents.core_agent import get_agent_executor
    print("Core agent compiled successfully.")
except Exception as e:
    print(f"Error compiling core agent: {e}")
    sys.exit(1)

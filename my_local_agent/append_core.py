import sys

with open("agents/core_agent.py", "r", encoding="utf-8") as f:
    content = f.read()

# Add imports
imports = """
    gestisci_calendario_mac, gestore_multimediale, parla_con_utente,
    trascrivi_e_riassumi_audio, gestisci_note_obsidian, esegui_comando_terminale_sandbox,
    gestisci_applicazioni_mac, pubblica_su_social
"""
content = content.replace("ricerca_nei_documenti_locali\n)", f"ricerca_nei_documenti_locali,{imports}\n)")

# Update DESKTOP_TOOLS
content = content.replace(
    "ricerca_nei_documenti_locali]", 
    "ricerca_nei_documenti_locali, gestore_multimediale, parla_con_utente, trascrivi_e_riassumi_audio, gestisci_note_obsidian, esegui_comando_terminale_sandbox, gestisci_applicazioni_mac]"
)

# Update COMMS_TOOLS
content = content.replace(
    "controlla_notifiche_discord]", 
    "controlla_notifiche_discord, gestisci_calendario_mac, pubblica_su_social]"
)

# Update supervisor_tools (we just put them before controlla_notifiche_discord)
content = content.replace(
    "controlla_notifiche_discord,", 
    "gestisci_calendario_mac, gestore_multimediale, parla_con_utente, trascrivi_e_riassumi_audio, gestisci_note_obsidian, esegui_comando_terminale_sandbox, gestisci_applicazioni_mac, pubblica_su_social, controlla_notifiche_discord,"
)

with open("agents/core_agent.py", "w", encoding="utf-8") as f:
    f.write(content)

print("Core agent updated successfully.")

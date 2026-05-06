import sys

with open("agents/core_agent.py", "r", encoding="utf-8") as f:
    content = f.read()

content = content.replace("gestisci_calendario_mac", "gestisci_calendario_universale")
content = content.replace("gestisci_applicazioni_mac", "gestisci_applicazioni_universale")

with open("agents/core_agent.py", "w", encoding="utf-8") as f:
    f.write(content)

print("Renaming successful.")

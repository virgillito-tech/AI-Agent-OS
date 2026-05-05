from langchain_core.utils.function_calling import convert_to_openai_tool
from tools.agent_tools import modifica_task_programmato, programma_task_autonomo
import json

schema = convert_to_openai_tool(modifica_task_programmato)
print(json.dumps(schema, indent=2))

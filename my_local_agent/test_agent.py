import asyncio
import os

# Imposta variabili ambiente prima di importare i moduli!
os.environ["MLX_BASE_URL"] = "http://localhost:8080"
os.environ["MLX_TEXT_MODEL_NAME"] = "mlx-community/Qwen3.5-9B-MLX-4bit"

from langchain_core.messages import HumanMessage
from agents.core_agent import get_agent_executor

async def main():
    agent = await get_agent_executor()
    inputs = {"messages": [HumanMessage(content="Modifica il mio task giornaliero delle 09:00 sulle novità AI, adesso voglio che sia una volta alla settimana il lunedì alle 7 del mattino, ok?")]}
    async for event in agent.astream_events(inputs, version="v2"):
        kind = event["event"]
        if kind == "on_chat_model_stream":
            chunk = event["data"]["chunk"]
            if chunk.content:
                print(chunk.content, end="", flush=True)
        elif kind == "on_tool_start":
            print(f"\n[TOOL START] {event['name']} - {event['data'].get('input')}")

if __name__ == "__main__":
    asyncio.run(main())

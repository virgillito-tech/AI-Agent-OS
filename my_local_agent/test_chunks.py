import asyncio
import os
os.environ["MLX_BASE_URL"] = "http://localhost:8080"

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage

async def main():
    llm = ChatOpenAI(
        model="mlx-community/Qwen3.5-9B-MLX-4bit",
        base_url="http://localhost:8080/v1",
        api_key="not-needed",
        temperature=0.0
    )
    messages = [
        {"role": "user", "content": "Risolvi questo enigma: Quanto fa 1+1? Mostra il ragionamento passo passo."}
    ]
    async for chunk in llm.astream(messages):
        if chunk.content or chunk.additional_kwargs or chunk.tool_call_chunks:
            print("CHUNK:", chunk.model_dump())

if __name__ == "__main__":
    asyncio.run(main())

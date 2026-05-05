from transformers import AutoTokenizer

tokenizer = AutoTokenizer.from_pretrained("mlx-community/Qwen3.5-9B-MLX-4bit")
messages = [
    {"role": "user", "content": "Modifica il mio task"},
    {"role": "assistant", "content": "", "tool_calls": [{"id": "call_1", "type": "function", "function": {"name": "modifica_task_programmato", "arguments": "{\"parola_chiave\": \"AI\"}"}}]},
    {"role": "tool", "tool_call_id": "call_1", "name": "modifica_task_programmato", "content": "Nessun task trovato."}
]

prompt = tokenizer.apply_chat_template(messages, tokenize=False)
print("FORMATTED PROMPT:")
print(prompt)

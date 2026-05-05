from transformers import AutoTokenizer

tokenizer = AutoTokenizer.from_pretrained("mlx-community/Qwen3.5-9B-MLX-4bit")
print("CHAT TEMPLATE:")
print(tokenizer.chat_template)

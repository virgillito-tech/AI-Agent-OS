import requests
import json

payload = {
    "model": "mlx-community/Qwen3.5-9B-MLX-4bit",
    "messages": [
        {"role": "user", "content": "Ciao"}
    ]
}

response = requests.post("http://localhost:8080/v1/chat/completions", json=payload)
print(json.dumps(response.json(), indent=2))

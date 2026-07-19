# pyrefly: ignore [missing-import]
from openai import OpenAI

client = OpenAI(
    base_url="https://api.nv.nvidia.com/v1/",
    api_key="[ENCRYPTION_KEY]",
)

response = client.chat.completions.create(
    model="google/gemma-3-12b-it",
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello, how are you?"},
    ],
)

print(response.choices[0].message.content)

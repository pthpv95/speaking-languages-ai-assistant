import os
from openai import OpenAI

key    = open(".env").read().split("\n")[0].split("=",1)[1].strip()
client = OpenAI(base_url="https://api.groq.com/openai/v1", api_key=key)
r = client.chat.completions.create(
    model="llama-3.3-70b-versatile",
    messages=[{"role":"user","content":"Say: key works"}],
    max_tokens=10,
)
print("OK:", r.choices[0].message.content)

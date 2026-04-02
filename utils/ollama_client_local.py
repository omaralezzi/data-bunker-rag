import requests

OLLAMA_BASE = "http://localhost:11434"

EMBED_MODEL = "nomic-embed-text"
CHAT_MODEL = "qwen3:14b"


def embed(text: str):
    r = requests.post(
        f"{OLLAMA_BASE}/api/embed",
        json={
            "model": EMBED_MODEL,
            "input": text
        },
        timeout=120
    )
    r.raise_for_status()
    return r.json()["embeddings"][0]


def chat(prompt: str, system: str = "") -> str:
    full_prompt = f"""System:
{system}

User:
{prompt}

Assistant:
"""

    r = requests.post(
        f"{OLLAMA_BASE}/api/generate",
        json={
            "model": CHAT_MODEL,
            "prompt": full_prompt,
            "stream": False
        },
        timeout=120
    )
    r.raise_for_status()
    return r.json()["response"].strip()
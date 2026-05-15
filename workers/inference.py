import os
import time
import httpx

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://ollama:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "tinyllama")
RAG_URL = os.getenv("RAG_URL", "http://localhost:8002")
RAG_TOP_K = int(os.getenv("RAG_TOP_K", "3"))


async def retrieve_context(prompt: str) -> str:
    async with httpx.AsyncClient(timeout=8.0) as client:
        try:
            resp = await client.get(
                f"{RAG_URL}/retrieve",
                params={"prompt": prompt, "top_k": RAG_TOP_K},
            )
            resp.raise_for_status()
            chunks = resp.json().get("chunks", [])
            return "\n\n".join(c["text"] for c in chunks)
        except Exception:
            return ""


async def run_inference(prompt: str, max_tokens: int) -> tuple[str, float]:
    start = time.time()
    context = await retrieve_context(prompt)
    user_content = f"[CONTEXT]\n{context}\n\n[QUESTION]\n{prompt}" if context else prompt

    async with httpx.AsyncClient(timeout=50.0) as client:
        resp = await client.post(
            f"{OLLAMA_URL}/api/chat",
            json={
                "model": OLLAMA_MODEL,
                "messages": [{"role": "user", "content": user_content}],
                "options": {"num_predict": max_tokens},
                "stream": False,
            },
        )
        resp.raise_for_status()
        response_text = resp.json()["message"]["content"]

    return response_text, (time.time() - start) * 1000

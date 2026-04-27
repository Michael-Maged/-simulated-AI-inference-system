import os
import time
import httpx

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "phi3:mini")
RAG_URL = os.getenv("RAG_URL", "http://localhost:8002")
RAG_TOP_K = int(os.getenv("RAG_TOP_K", "3"))


async def retrieve_context(prompt: str) -> str:
    async with httpx.AsyncClient(timeout=10.0) as client:
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
    full_prompt = f"[CONTEXT]\n{context}\n\n[QUESTION]\n{prompt}" if context else prompt

    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(
            f"{OLLAMA_URL}/api/generate",
            json={
                "model": OLLAMA_MODEL,
                "prompt": full_prompt,
                "stream": False,
                "options": {"num_predict": max_tokens},
            },
        )
        resp.raise_for_status()
        response_text = resp.json()["response"]

    return response_text, (time.time() - start) * 1000

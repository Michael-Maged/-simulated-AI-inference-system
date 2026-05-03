import os
import time
import httpx

GROK_API_KEY = os.getenv("GROQ_API_KEY", "")
GROK_MODEL = os.getenv("GROK_MODEL", "llama-3.1-8b-instant")
GROK_API_URL = "https://api.groq.com/openai/v1/chat/completions"
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
    user_content = f"[CONTEXT]\n{context}\n\n[QUESTION]\n{prompt}" if context else prompt

    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(
            GROK_API_URL,
            headers={"Authorization": f"Bearer {GROK_API_KEY}"},
            json={
                "model": GROK_MODEL,
                "messages": [{"role": "user", "content": user_content}],
                "max_tokens": max_tokens,
            },
        )
        resp.raise_for_status()
        response_text = resp.json()["choices"][0]["message"]["content"]

    return response_text, (time.time() - start) * 1000

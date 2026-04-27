import json
import numpy as np
import redis.asyncio as aioredis
from sentence_transformers import SentenceTransformer


class SemanticCache:
    def __init__(self, redis_url: str, threshold: float, ttl: int, model_name: str):
        self.redis = aioredis.from_url(redis_url, decode_responses=False)
        self.threshold = threshold
        self.ttl = ttl
        self.model = SentenceTransformer(model_name)

    async def get(self, prompt: str) -> str | None:
        keys = await self.redis.keys("cache:embed:*")
        if not keys:
            return None
        query_embed = self.model.encode([prompt])[0]
        for key in keys:
            raw = await self.redis.get(key)
            if not raw:
                continue
            entry = json.loads(raw)
            cached_embed = np.array(entry["embedding"])
            norm = np.linalg.norm(query_embed) * np.linalg.norm(cached_embed)
            if norm == 0:
                continue
            sim = float(np.dot(query_embed, cached_embed) / norm)
            if sim >= self.threshold:
                return entry["response"]
        return None

    async def set(self, prompt: str, response: str) -> None:
        embed = self.model.encode([prompt])[0].tolist()
        key = f"cache:embed:{abs(hash(prompt))}"
        data = json.dumps({"embedding": embed, "response": response})
        await self.redis.setex(key, self.ttl, data)

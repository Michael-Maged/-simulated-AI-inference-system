import asyncio
from typing import List


class RoundRobinStrategy:
    def __init__(self):
        self._index = 0
        self._lock = asyncio.Lock()

    async def pick(self, workers: List[str]) -> str:
        async with self._lock:
            worker = workers[self._index % len(workers)]
            self._index += 1
            return worker


class LeastConnectionsStrategy:
    async def pick(self, workers: List[str], redis) -> str:
        min_conn = float("inf")
        best = workers[0]
        for w in workers:
            raw = await redis.get(f"connections:{w}")
            conn = int(raw) if raw is not None else 0
            if conn < min_conn:
                min_conn = conn
                best = w
        return best


class LoadAwareStrategy:
    async def pick(self, workers: List[str], redis) -> str:
        min_p95 = float("inf")
        best = None
        for w in workers:
            raw = await redis.get(f"p95:{w}")
            if raw is not None:
                p95 = float(raw)
                if p95 < min_p95:
                    min_p95 = p95
                    best = w
        if best is None:
            return await LeastConnectionsStrategy().pick(workers, redis)
        return best

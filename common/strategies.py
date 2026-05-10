"""
Load-balancing strategies. Canonical home is here in ``common/`` so both the
load_balancer and master services can import the same implementation.

All three strategies share the signature ``async pick(workers, redis=None) -> str``
where ``workers`` is a list of worker_id strings. RoundRobin ignores the redis
argument; LeastConnections and LoadAware use it to read live counters.
"""
import asyncio
from typing import List, Optional


class RoundRobinStrategy:
    """Cycles through workers in a fixed order. O(1) per pick, no Redis call."""

    def __init__(self):
        self._index = 0
        self._lock = asyncio.Lock()

    async def pick(self, workers: List[str], redis=None) -> str:
        if not workers:
            raise ValueError("RoundRobinStrategy.pick: no workers provided")
        async with self._lock:
            worker = workers[self._index % len(workers)]
            self._index += 1
            return worker


class LeastConnectionsStrategy:
    """Picks the worker with the lowest live connection count from Redis."""

    async def pick(self, workers: List[str], redis=None) -> str:
        if not workers:
            raise ValueError("LeastConnectionsStrategy.pick: no workers provided")
        if redis is None:
            return workers[0]
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
    """
    Picks the worker with the lowest reported p95 latency. Falls back to
    LeastConnections when no p95 data has been reported yet (e.g. cold start).
    """

    async def pick(self, workers: List[str], redis=None) -> str:
        if not workers:
            raise ValueError("LoadAwareStrategy.pick: no workers provided")
        if redis is None:
            return workers[0]
        min_p95 = float("inf")
        best: Optional[str] = None
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


def make_strategy(name: str):
    """Factory used by master and tests."""
    name = (name or "round_robin").lower()
    if name == "round_robin":
        return RoundRobinStrategy()
    if name == "least_connections":
        return LeastConnectionsStrategy()
    if name == "load_aware":
        return LoadAwareStrategy()
    raise ValueError(f"Unknown strategy: {name}")

import time
from dataclasses import dataclass
from typing import Dict, List


@dataclass
class WorkerInfo:
    worker_id: str
    host: str
    port: int
    alive: bool = False
    last_heartbeat: float = 0.0
    queue_depth: int = 0
    last_latency_ms: float = 9999.0


class WorkerRegistry:
    def __init__(self, redis, timeout: int = 15):
        self.redis = redis
        self.timeout = timeout
        self._workers: Dict[str, WorkerInfo] = {}

    def register_worker(self, worker_id: str, host: str, port: int) -> None:
        # Always update host/port — worker may have restarted with a new container hostname
        self._workers[worker_id] = WorkerInfo(worker_id=worker_id, host=host, port=port)

    async def heartbeat(self, worker_id: str, queue_depth: int, last_latency_ms: float, host: str = "", port: int = 9001) -> None:
        if worker_id not in self._workers:
            if host:
                self.register_worker(worker_id, host, port)
            else:
                return
        w = self._workers[worker_id]
        now = time.time()
        w.last_heartbeat = now
        w.queue_depth = queue_depth
        w.last_latency_ms = last_latency_ms
        w.alive = True
        await self.redis.set(f"heartbeat:{worker_id}", now)
        await self.redis.set(f"p95:{worker_id}", last_latency_ms)

    async def check_health(self) -> None:
        now = time.time()
        evict = []
        for w in self._workers.values():
            raw = await self.redis.get(f"heartbeat:{w.worker_id}")
            if raw is None or (now - float(raw)) > self.timeout:
                w.alive = False
                # evict workers silent for >3x timeout (they're gone for good)
                if raw is None or (now - float(raw)) > self.timeout * 10:
                    evict.append(w.worker_id)
            else:
                w.alive = True
        for wid in evict:
            self._workers.pop(wid, None)

    def get_healthy_workers(self) -> List[WorkerInfo]:
        return [w for w in self._workers.values() if w.alive]

    def all_workers(self) -> List[WorkerInfo]:
        return list(self._workers.values())

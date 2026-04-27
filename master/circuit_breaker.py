import time
from enum import Enum


class CircuitState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    def __init__(self, worker_id: str, redis, threshold: int = 5, cooldown: int = 30):
        self.worker_id = worker_id
        self.redis = redis
        self.threshold = threshold
        self.cooldown = cooldown

    async def get_state(self) -> CircuitState:
        raw = await self.redis.get(f"cb:state:{self.worker_id}")
        if raw is None:
            return CircuitState.CLOSED
        return CircuitState(raw.decode() if isinstance(raw, bytes) else raw)

    async def record_success(self) -> None:
        state = await self.get_state()
        if state == CircuitState.HALF_OPEN:
            await self.redis.set(f"cb:state:{self.worker_id}", CircuitState.CLOSED)
            await self.redis.delete(f"cb:failures:{self.worker_id}")

    async def record_failure(self) -> None:
        failures = await self.redis.incr(f"cb:failures:{self.worker_id}")
        if failures >= self.threshold:
            await self.redis.set(f"cb:state:{self.worker_id}", CircuitState.OPEN)
            await self.redis.set(f"cb:opened_at:{self.worker_id}", time.time())

    async def check_and_transition(self) -> CircuitState:
        state = await self.get_state()
        if state == CircuitState.OPEN:
            raw = await self.redis.get(f"cb:opened_at:{self.worker_id}")
            if raw and (time.time() - float(raw)) >= self.cooldown:
                await self.redis.set(f"cb:state:{self.worker_id}", CircuitState.HALF_OPEN)
                return CircuitState.HALF_OPEN
        return state

    async def is_available(self) -> bool:
        state = await self.check_and_transition()
        return state in (CircuitState.CLOSED, CircuitState.HALF_OPEN)

import asyncio
import logging
import sys
from concurrent.futures import ThreadPoolExecutor

import grpc

sys.path.insert(0, "/app")
sys.path.insert(0, "/app/common/protos")
from common.protos import worker_pb2, worker_pb2_grpc
from circuit_breaker import CircuitBreaker

log = logging.getLogger(__name__)

# Max requests waiting in queue per worker before rejecting
MAX_QUEUE_DEPTH = int(__import__("os").getenv("MAX_QUEUE_DEPTH", "50"))


async def dispatch_to_worker(
    worker_info,
    request_id: str,
    prompt: str,
    max_tokens: int,
    circuit_breaker: CircuitBreaker,
) -> dict:
    address = f"{worker_info.host}:{worker_info.port}"
    loop = asyncio.get_event_loop()
    def _call():
        with grpc.insecure_channel(address) as channel:
            stub = worker_pb2_grpc.WorkerStub(channel)
            return stub.Infer(
                worker_pb2.InferRequest(
                    request_id=request_id,
                    prompt=prompt,
                    max_tokens=max_tokens,
                    priority="normal",
                ),
                timeout=120.0,
            )
    try:
        response = await loop.run_in_executor(None, _call)
        await circuit_breaker.record_success()
        return {
            "request_id": response.request_id,
            "response": response.response,
            "latency_ms": response.latency_ms,
            "worker_id": response.worker_id,
        }
    except Exception as e:
        await circuit_breaker.record_failure()
        raise RuntimeError(f"Worker {address} failed: {e}") from e


async def process_request(
    redis,
    registry,
    circuit_breakers: dict,
    request_id: str,
    prompt: str,
    max_tokens: int,
    max_retries: int = 3,
) -> dict:
    # Wait for a healthy available worker instead of immediately failing
    for wait_attempt in range(20):
        healthy = registry.get_healthy_workers()
        if not healthy:
            raise RuntimeError("No healthy workers available")

        # Find workers with queue capacity
        candidates = []
        for w in healthy:
            cb = circuit_breakers[w.worker_id]
            if not await cb.is_available():
                continue
            depth = int(await redis.get(f"connections:{w.worker_id}") or 0)
            if depth < MAX_QUEUE_DEPTH:
                candidates.append((depth, w))

        if candidates:
            candidates.sort(key=lambda x: x[0])
            break

        # All workers busy — wait and retry
        log.info(f"All workers at capacity, waiting... (attempt {wait_attempt + 1})")
        await asyncio.sleep(1)
    else:
        raise RuntimeError("All workers at max capacity after waiting")

    last_error = None
    tried: set = set()

    for _ in range(max_retries):
        available = [(d, w) for d, w in candidates if w.worker_id not in tried]
        if not available:
            break
        _, worker = available[0]
        tried.add(worker.worker_id)
        cb = circuit_breakers[worker.worker_id]
        await redis.incr(f"connections:{worker.worker_id}")
        try:
            result = await dispatch_to_worker(worker, request_id, prompt, max_tokens, cb)
            return result
        except RuntimeError as e:
            last_error = e
            log.warning(f"Worker {worker.worker_id} failed, trying next: {e}")
            # Re-sort remaining candidates on failure
            candidates = [(d, w) for d, w in candidates if w.worker_id not in tried]
        finally:
            await redis.decr(f"connections:{worker.worker_id}")

    await redis.lpush("queue:failed", f"{request_id}:{prompt[:50]}")
    raise RuntimeError(f"All retries exhausted: {last_error}")

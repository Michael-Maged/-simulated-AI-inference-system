import asyncio
import logging
import sys

import grpc

sys.path.insert(0, "/app")
sys.path.insert(0, "/app/common/protos")
from common.protos import worker_pb2, worker_pb2_grpc
from circuit_breaker import CircuitBreaker

log = logging.getLogger(__name__)


async def dispatch_to_worker(
    worker_info,
    request_id: str,
    prompt: str,
    max_tokens: int,
    circuit_breaker: CircuitBreaker,
) -> dict:
    address = f"{worker_info.host}:{worker_info.port}"
    async with grpc.aio.insecure_channel(address) as channel:
        stub = worker_pb2_grpc.WorkerStub(channel)
        try:
            response = await asyncio.wait_for(
                stub.Infer(worker_pb2.InferRequest(
                    request_id=request_id,
                    prompt=prompt,
                    max_tokens=max_tokens,
                    priority="normal",
                )),
                timeout=120.0,
            )
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
    healthy = registry.get_healthy_workers()
    if not healthy:
        raise RuntimeError("No healthy workers available")

    last_error = None
    tried: set = set()

    for _ in range(max_retries):
        candidates = [w for w in healthy if w.worker_id not in tried]
        if not candidates:
            break
        for worker in candidates:
            cb = circuit_breakers[worker.worker_id]
            if not await cb.is_available():
                tried.add(worker.worker_id)
                continue
            tried.add(worker.worker_id)
            await redis.incr(f"connections:{worker.worker_id}")
            try:
                result = await dispatch_to_worker(worker, request_id, prompt, max_tokens, cb)
                return result
            except RuntimeError as e:
                last_error = e
                log.warning(f"Worker {worker.worker_id} failed, trying next: {e}")
            finally:
                await redis.decr(f"connections:{worker.worker_id}")

    await redis.lpush("queue:failed", f"{request_id}:{prompt[:50]}")
    raise RuntimeError(f"All retries exhausted: {last_error}")

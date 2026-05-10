"""
End-to-end test that the master's process_request actually invokes the
configured strategy when picking a worker. Regression guard against the
"strategy constructed but never called" bug.
"""
import sys
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, ".")
sys.path.insert(0, "./master")

# Stub gRPC modules before queue_processor imports them
sys.modules.setdefault("common.protos", MagicMock())
sys.modules.setdefault("common.protos.worker_pb2", MagicMock())
sys.modules.setdefault("common.protos.worker_pb2_grpc", MagicMock())

from master.queue_processor import process_request  # noqa: E402


class _Worker:
    def __init__(self, worker_id):
        self.worker_id = worker_id
        self.host = worker_id
        self.port = 9001


@pytest.mark.asyncio
async def test_round_robin_cycles_workers_via_master():
    """Three /dispatch calls under round_robin must hit w1, w2, w3 in order."""
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=None)        # 0 connections, no p95
    redis.incr = AsyncMock()
    redis.decr = AsyncMock()
    redis.lpush = AsyncMock()

    registry = MagicMock()
    registry.get_healthy_workers.return_value = [_Worker("w1"), _Worker("w2"), _Worker("w3")]

    cb = MagicMock()
    cb.is_available = AsyncMock(return_value=True)
    cb.record_success = AsyncMock()
    cb.record_failure = AsyncMock()
    breakers = {"w1": cb, "w2": cb, "w3": cb}

    cache = {}
    picked = []

    async def fake_dispatch(worker_info, request_id, prompt, max_tokens, breaker):
        picked.append(worker_info.worker_id)
        return {"request_id": request_id, "response": "ok",
                "latency_ms": 10.0, "worker_id": worker_info.worker_id}

    with patch("master.queue_processor.dispatch_to_worker", new=fake_dispatch):
        for i in range(3):
            await process_request(
                redis, registry, breakers,
                f"req-{i}", "hi", 64, 1,
                strategy_name="round_robin", strategy_cache=cache,
            )
    assert picked == ["w1", "w2", "w3"]


@pytest.mark.asyncio
async def test_least_connections_picks_lowest_via_master():
    """least_connections must pick the worker whose connections key is lowest."""
    redis = AsyncMock()
    redis.get = AsyncMock(side_effect=lambda k: {
        "connections:w1": b"3",
        "connections:w2": b"1",
        "connections:w3": b"5",
    }.get(k))
    redis.incr = AsyncMock()
    redis.decr = AsyncMock()
    redis.lpush = AsyncMock()

    registry = MagicMock()
    registry.get_healthy_workers.return_value = [_Worker("w1"), _Worker("w2"), _Worker("w3")]

    cb = MagicMock()
    cb.is_available = AsyncMock(return_value=True)
    cb.record_success = AsyncMock()
    cb.record_failure = AsyncMock()
    breakers = {"w1": cb, "w2": cb, "w3": cb}

    picked = []
    async def fake_dispatch(worker_info, *_args, **_kw):
        picked.append(worker_info.worker_id)
        return {"request_id": "x", "response": "ok",
                "latency_ms": 1.0, "worker_id": worker_info.worker_id}

    with patch("master.queue_processor.dispatch_to_worker", new=fake_dispatch):
        await process_request(
            redis, registry, breakers,
            "req-1", "hi", 64, 1,
            strategy_name="least_connections", strategy_cache={},
        )
    assert picked == ["w2"]


@pytest.mark.asyncio
async def test_load_aware_picks_lowest_p95_via_master():
    """load_aware must pick the worker whose p95 key is lowest."""
    p95_table = {"p95:w1": b"500.0", "p95:w2": b"100.0", "p95:w3": b"300.0"}

    async def _get(k):
        # connections all 0; p95 from table
        if k.startswith("connections:"):
            return None
        return p95_table.get(k)

    redis = AsyncMock()
    redis.get = AsyncMock(side_effect=_get)
    redis.incr = AsyncMock()
    redis.decr = AsyncMock()
    redis.lpush = AsyncMock()

    registry = MagicMock()
    registry.get_healthy_workers.return_value = [_Worker("w1"), _Worker("w2"), _Worker("w3")]

    cb = MagicMock()
    cb.is_available = AsyncMock(return_value=True)
    cb.record_success = AsyncMock()
    cb.record_failure = AsyncMock()
    breakers = {"w1": cb, "w2": cb, "w3": cb}

    picked = []
    async def fake_dispatch(worker_info, *_args, **_kw):
        picked.append(worker_info.worker_id)
        return {"request_id": "x", "response": "ok",
                "latency_ms": 1.0, "worker_id": worker_info.worker_id}

    with patch("master.queue_processor.dispatch_to_worker", new=fake_dispatch):
        await process_request(
            redis, registry, breakers,
            "req-1", "hi", 64, 1,
            strategy_name="load_aware", strategy_cache={},
        )
    assert picked == ["w2"]

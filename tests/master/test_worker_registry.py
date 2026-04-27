import pytest
import time
from unittest.mock import AsyncMock
import sys
sys.path.insert(0, ".")

from master.worker_registry import WorkerRegistry


@pytest.fixture
def mock_redis():
    r = AsyncMock()
    r.set = AsyncMock()
    r.get = AsyncMock(return_value=None)
    return r


def test_register_worker_adds_to_registry(mock_redis):
    reg = WorkerRegistry(mock_redis, timeout=15)
    reg.register_worker("w1", "worker-1", 9001)
    assert "w1" in reg._workers
    assert reg._workers["w1"].host == "worker-1"


@pytest.mark.asyncio
async def test_heartbeat_marks_worker_alive(mock_redis):
    reg = WorkerRegistry(mock_redis, timeout=15)
    reg.register_worker("w1", "worker-1", 9001)
    await reg.heartbeat("w1", queue_depth=2, last_latency_ms=150.0)
    assert reg._workers["w1"].alive is True
    assert reg._workers["w1"].queue_depth == 2


@pytest.mark.asyncio
async def test_check_health_marks_stale_worker_dead(mock_redis):
    mock_redis.get = AsyncMock(return_value=str(time.time() - 20).encode())
    reg = WorkerRegistry(mock_redis, timeout=15)
    reg.register_worker("w1", "worker-1", 9001)
    reg._workers["w1"].alive = True
    await reg.check_health()
    assert reg._workers["w1"].alive is False


@pytest.mark.asyncio
async def test_check_health_keeps_recent_worker_alive(mock_redis):
    mock_redis.get = AsyncMock(return_value=str(time.time()).encode())
    reg = WorkerRegistry(mock_redis, timeout=15)
    reg.register_worker("w1", "worker-1", 9001)
    await reg.check_health()
    assert reg._workers["w1"].alive is True


def test_get_healthy_workers_filters_dead(mock_redis):
    reg = WorkerRegistry(mock_redis, timeout=15)
    reg.register_worker("w1", "worker-1", 9001)
    reg.register_worker("w2", "worker-2", 9002)
    reg._workers["w1"].alive = True
    reg._workers["w2"].alive = False
    healthy = reg.get_healthy_workers()
    assert len(healthy) == 1
    assert healthy[0].worker_id == "w1"

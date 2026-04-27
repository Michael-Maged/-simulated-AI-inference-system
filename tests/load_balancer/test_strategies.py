import asyncio
import pytest
from unittest.mock import AsyncMock
import sys
sys.path.insert(0, ".")

from load_balancer.strategies import RoundRobinStrategy, LeastConnectionsStrategy, LoadAwareStrategy


@pytest.mark.asyncio
async def test_round_robin_cycles_through_workers():
    strategy = RoundRobinStrategy()
    workers = ["w1", "w2", "w3"]
    results = [await strategy.pick(workers) for _ in range(6)]
    assert results == ["w1", "w2", "w3", "w1", "w2", "w3"]


@pytest.mark.asyncio
async def test_round_robin_single_worker():
    strategy = RoundRobinStrategy()
    assert await strategy.pick(["only"]) == "only"


@pytest.mark.asyncio
async def test_least_connections_picks_lowest():
    redis = AsyncMock()
    redis.get = AsyncMock(side_effect=lambda k: {
        "connections:w1": b"5",
        "connections:w2": b"2",
        "connections:w3": b"8",
    }.get(k))
    strategy = LeastConnectionsStrategy()
    result = await strategy.pick(["w1", "w2", "w3"], redis)
    assert result == "w2"


@pytest.mark.asyncio
async def test_least_connections_handles_no_data():
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=None)
    strategy = LeastConnectionsStrategy()
    result = await strategy.pick(["w1", "w2"], redis)
    assert result in ["w1", "w2"]


@pytest.mark.asyncio
async def test_load_aware_picks_lowest_p95():
    redis = AsyncMock()
    redis.get = AsyncMock(side_effect=lambda k: {
        "p95:w1": b"200.0",
        "p95:w2": b"80.0",
        "p95:w3": b"150.0",
    }.get(k))
    strategy = LoadAwareStrategy()
    result = await strategy.pick(["w1", "w2", "w3"], redis)
    assert result == "w2"


@pytest.mark.asyncio
async def test_load_aware_falls_back_to_least_conn_when_no_data():
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=None)
    strategy = LoadAwareStrategy()
    result = await strategy.pick(["w1", "w2"], redis)
    assert result in ["w1", "w2"]

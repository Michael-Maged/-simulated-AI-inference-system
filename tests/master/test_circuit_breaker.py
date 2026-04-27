import pytest
import time
from unittest.mock import AsyncMock
import sys
sys.path.insert(0, ".")

from master.circuit_breaker import CircuitBreaker, CircuitState


@pytest.fixture
def redis():
    r = AsyncMock()
    r.get = AsyncMock(return_value=None)
    r.set = AsyncMock()
    r.incr = AsyncMock(return_value=1)
    r.delete = AsyncMock()
    return r


@pytest.mark.asyncio
async def test_initial_state_is_closed(redis):
    cb = CircuitBreaker("w1", redis, threshold=5, cooldown=30)
    assert await cb.get_state() == CircuitState.CLOSED


@pytest.mark.asyncio
async def test_trips_to_open_after_threshold_failures(redis):
    redis.incr = AsyncMock(return_value=5)
    cb = CircuitBreaker("w1", redis, threshold=5, cooldown=30)
    await cb.record_failure()
    redis.set.assert_any_call("cb:state:w1", CircuitState.OPEN)


@pytest.mark.asyncio
async def test_does_not_trip_below_threshold(redis):
    redis.incr = AsyncMock(return_value=4)
    cb = CircuitBreaker("w1", redis, threshold=5, cooldown=30)
    await cb.record_failure()
    calls = [str(c) for c in redis.set.call_args_list]
    assert not any("open" in c.lower() for c in calls)


@pytest.mark.asyncio
async def test_success_in_half_open_closes_circuit(redis):
    redis.get = AsyncMock(return_value=b"half_open")
    cb = CircuitBreaker("w1", redis, threshold=5, cooldown=30)
    await cb.record_success()
    redis.set.assert_any_call("cb:state:w1", CircuitState.CLOSED)


@pytest.mark.asyncio
async def test_open_transitions_to_half_open_after_cooldown(redis):
    redis.get = AsyncMock(side_effect=[b"open", str(time.time() - 35).encode()])
    cb = CircuitBreaker("w1", redis, threshold=5, cooldown=30)
    assert await cb.check_and_transition() == CircuitState.HALF_OPEN


@pytest.mark.asyncio
async def test_open_stays_open_within_cooldown(redis):
    redis.get = AsyncMock(side_effect=[b"open", str(time.time() - 10).encode()])
    cb = CircuitBreaker("w1", redis, threshold=5, cooldown=30)
    assert await cb.check_and_transition() == CircuitState.OPEN


@pytest.mark.asyncio
async def test_is_available_true_when_closed(redis):
    cb = CircuitBreaker("w1", redis, threshold=5, cooldown=30)
    assert await cb.is_available() is True


@pytest.mark.asyncio
async def test_is_available_false_when_open(redis):
    redis.get = AsyncMock(side_effect=[b"open", str(time.time()).encode()])
    cb = CircuitBreaker("w1", redis, threshold=5, cooldown=30)
    assert await cb.is_available() is False

import pytest
import json
import numpy as np
from unittest.mock import AsyncMock, MagicMock
import sys
sys.path.insert(0, ".")


@pytest.fixture
def mock_redis():
    r = AsyncMock()
    r.keys = AsyncMock(return_value=[])
    r.get = AsyncMock(return_value=None)
    r.setex = AsyncMock(return_value=True)
    return r


@pytest.fixture
def mock_model():
    model = MagicMock()
    model.encode = MagicMock(return_value=np.array([[0.1, 0.2, 0.3]]))
    return model


@pytest.mark.asyncio
async def test_cache_miss_returns_none(mock_redis, mock_model):
    from load_balancer.cache import SemanticCache
    cache = SemanticCache.__new__(SemanticCache)
    cache.redis = mock_redis
    cache.threshold = 0.88
    cache.ttl = 3600
    cache.model = mock_model
    result = await cache.get("What is AI?")
    assert result is None


@pytest.mark.asyncio
async def test_cache_hit_returns_response(mock_redis, mock_model):
    from load_balancer.cache import SemanticCache
    embed = [0.1, 0.2, 0.3]
    cached_entry = json.dumps({"embedding": embed, "response": "AI is cool"})
    mock_redis.keys = AsyncMock(return_value=[b"cache:embed:123"])
    mock_redis.get = AsyncMock(return_value=cached_entry.encode())
    cache = SemanticCache.__new__(SemanticCache)
    cache.redis = mock_redis
    cache.threshold = 0.88
    cache.ttl = 3600
    cache.model = mock_model
    result = await cache.get("What is AI?")
    assert result == "AI is cool"


@pytest.mark.asyncio
async def test_cache_set_stores_embedding(mock_redis, mock_model):
    from load_balancer.cache import SemanticCache
    cache = SemanticCache.__new__(SemanticCache)
    cache.redis = mock_redis
    cache.threshold = 0.88
    cache.ttl = 3600
    cache.model = mock_model
    await cache.set("What is AI?", "AI is cool")
    assert mock_redis.setex.called
    call_args = mock_redis.setex.call_args
    assert call_args[0][1] == 3600
    stored = json.loads(call_args[0][2])
    assert stored["response"] == "AI is cool"
    assert "embedding" in stored

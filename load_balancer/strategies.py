"""
Backwards-compatible re-export. Canonical implementation lives in
``common/strategies.py`` so the master service can use the same module.
"""
from common.strategies import (  # noqa: F401
    RoundRobinStrategy,
    LeastConnectionsStrategy,
    LoadAwareStrategy,
    make_strategy,
)

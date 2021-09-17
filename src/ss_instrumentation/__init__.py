from __future__ import (
    absolute_import,
)

__version__ = "2.0.0"

from .SSInstrumentation import (
    InMemoryMetricStorage,
    RedisMetricStorage,
    SSInstrumentation,
)

__all__ = [
    "__version__",
    "SSInstrumentation",
    "InMemoryMetricStorage",
    "RedisMetricStorage",
]

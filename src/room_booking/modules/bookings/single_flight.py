"""Deduplicate in-flight async work by key: only one task runs per key at a time."""

import asyncio
from collections.abc import Callable


class SingleFlight[T, K]:
    """
    Run a task keyed by K. If another call with the same key is in progress,
    await that task instead of starting a new one. Supports many keys; each key
    has at most one in-flight task. Keys are compared by key_eq (default ==).
    Clear stored task on exception.
    """

    _pairs: list[tuple[K, asyncio.Task[T]]]
    _key_eq: Callable[[K, K], bool]
    _lock: asyncio.Lock

    def __init__(self, *, key_eq: Callable[[K, K], bool] | None = None) -> None:
        self._pairs = []
        self._key_eq = key_eq if key_eq is not None else (lambda a, b: a == b)
        self._lock = asyncio.Lock()

    def _find(self, key: K) -> int:
        for i, (k, _) in enumerate(self._pairs):
            if self._key_eq(k, key):
                return i
        return -1

    async def run(
        self,
        key: K,
        create_task_func: Callable[[], asyncio.Task[T]],
        *,
        use_dedup: bool = True,
    ) -> T:
        async with self._lock:
            idx = self._find(key)
            existing = self._pairs[idx][1] if idx >= 0 else None
            if not use_dedup or existing is None or existing.done():
                task = create_task_func()
                if idx >= 0:
                    self._pairs[idx] = (key, task)
                else:
                    self._pairs.append((key, task))
            else:
                task = existing
        try:
            return await task
        finally:
            async with self._lock:
                idx = self._find(key)
                if idx >= 0 and self._pairs[idx][1] is task:
                    self._pairs.pop(idx)

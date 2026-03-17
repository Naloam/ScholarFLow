from __future__ import annotations

from collections import defaultdict, deque
from time import time

from config.settings import settings


WINDOW_SECONDS = 60.0
_REQUEST_BUCKETS: dict[str, deque[float]] = defaultdict(deque)


def clear_rate_limit_state() -> None:
    _REQUEST_BUCKETS.clear()


def consume_rate_limit(key: str, now: float | None = None) -> tuple[bool, int]:
    limit = settings.rate_limit_requests_per_minute
    if limit <= 0:
        return True, 0

    current_time = now if now is not None else time()
    bucket = _REQUEST_BUCKETS[key]
    while bucket and current_time - bucket[0] >= WINDOW_SECONDS:
        bucket.popleft()

    if len(bucket) >= limit:
        retry_after = max(1, int(WINDOW_SECONDS - (current_time - bucket[0])))
        return False, retry_after

    bucket.append(current_time)
    return True, 0

"""
Per-user in-memory rate limiter.
Gemini's free tier allows ~15 requests/minute — we cap at 10/minute per user
to stay safely under that, and 100/day per user to avoid burning quota.
"""

import time
from collections import defaultdict, deque

MAX_PER_MINUTE = 10
MAX_PER_DAY = 100

_minute_hits = defaultdict(deque)
_day_hits = defaultdict(deque)


def check_rate_limit(user_id: str = "default"):
    """Returns (allowed: bool, message: str)."""
    now = time.time()
    minute_q = _minute_hits[user_id]
    day_q = _day_hits[user_id]

    while minute_q and now - minute_q[0] > 60:
        minute_q.popleft()
    while day_q and now - day_q[0] > 86400:
        day_q.popleft()

    if len(minute_q) >= MAX_PER_MINUTE:
        return False, "Rate limit hit: too many questions in the last minute. Wait a moment and try again."

    if len(day_q) >= MAX_PER_DAY:
        return False, "Daily question limit reached. Try again tomorrow, or upgrade your Gemini API tier."

    minute_q.append(now)
    day_q.append(now)
    return True, ""

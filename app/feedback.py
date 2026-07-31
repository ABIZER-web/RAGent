"""
Feedback logging.
Stores thumbs up/down on answers to a per-user JSON log — useful for a
project report section on "real-world iteration" and identifying weak spots.
"""

import os
import json
import time

FEEDBACK_DIR = "data/feedback"
os.makedirs(FEEDBACK_DIR, exist_ok=True)


def _path(user_id: str):
    return os.path.join(FEEDBACK_DIR, f"{user_id}.json")


def log_feedback(user_id: str, question: str, answer: str, rating: str):
    """rating: 'up' or 'down'"""
    path = _path(user_id)
    entries = []
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            entries = json.load(f)

    entries.append({
        "question": question,
        "answer": answer,
        "rating": rating,
        "timestamp": time.time(),
    })

    with open(path, "w", encoding="utf-8") as f:
        json.dump(entries, f)

    return len(entries)


def get_feedback_summary(user_id: str):
    path = _path(user_id)
    if not os.path.exists(path):
        return {"up": 0, "down": 0, "total": 0}

    with open(path, "r", encoding="utf-8") as f:
        entries = json.load(f)

    up = sum(1 for e in entries if e["rating"] == "up")
    down = sum(1 for e in entries if e["rating"] == "down")
    return {"up": up, "down": down, "total": len(entries)}

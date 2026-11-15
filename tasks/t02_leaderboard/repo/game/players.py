"""Player bookkeeping."""
from collections import defaultdict


class ScoreBook:
    def __init__(self):
        self._scores = defaultdict(int)

    def add(self, name: str, points: int) -> None:
        if points < 0:
            raise ValueError("points must be non-negative")
        self._scores[name] += points

    def as_dict(self) -> dict:
        return dict(self._scores)

    def __len__(self) -> int:
        return len(self._scores)

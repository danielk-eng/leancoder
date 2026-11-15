"""Hit/miss counters."""


class Counter:
    def __init__(self):
        self.hits = 0
        self.misses = 0

    def ratio(self) -> float:
        total = self.hits + self.misses
        return self.hits / total if total else 0.0

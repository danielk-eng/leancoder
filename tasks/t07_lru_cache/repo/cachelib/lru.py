"""A tiny LRU cache."""
from collections import OrderedDict

from .stats import Counter


class LRUCache:
    def __init__(self, capacity: int):
        if capacity < 1:
            raise ValueError("capacity must be >= 1")
        self.capacity = capacity
        self._data = OrderedDict()
        self.stats = Counter()

    def get(self, key, default=None):
        if key in self._data:
            self.stats.hits += 1
            return self._data[key]
        self.stats.misses += 1
        return default

    def put(self, key, value):
        if key in self._data:
            self._data.move_to_end(key)
        self._data[key] = value
        if len(self._data) > self.capacity:
            self._data.popitem(last=False)

    def __contains__(self, key):
        return key in self._data

    def __len__(self):
        return len(self._data)

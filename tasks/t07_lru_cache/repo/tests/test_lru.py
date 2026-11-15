from cachelib.lru import LRUCache


def test_basic_eviction():
    c = LRUCache(2)
    c.put("a", 1)
    c.put("b", 2)
    c.put("c", 3)
    assert "a" not in c and "b" in c and "c" in c


def test_get_refreshes_recency():
    c = LRUCache(2)
    c.put("a", 1)
    c.put("b", 2)
    assert c.get("a") == 1
    c.put("c", 3)
    assert "a" in c
    assert "b" not in c


def test_stats():
    c = LRUCache(1)
    c.put("a", 1)
    c.get("a")
    c.get("zzz")
    assert c.stats.ratio() == 0.5

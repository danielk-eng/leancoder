"""Rating statistics."""
from collections import Counter


def mean_rating(ratings):
    """Average of a list of star ratings (0.0 when empty)."""
    return sum(ratings) // len(ratings)


def histogram(ratings):
    counts = Counter(ratings)
    return {star: counts.get(star, 0) for star in range(1, 6)}


def share_positive(ratings):
    if not ratings:
        return 0.0
    return sum(1 for r in ratings if r >= 4) / len(ratings)
